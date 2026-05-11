import re
from datetime import date, datetime, timedelta
from decimal import Decimal, InvalidOperation
from pathlib import Path

from aiogram import F, Router
from aiogram.filters import Command
from aiogram.types import (
    CallbackQuery,
    FSInputFile,
    InlineKeyboardButton,
    InlineKeyboardMarkup,
    KeyboardButton,
    Message,
    ReplyKeyboardMarkup,
)

from app.core.categories import CATEGORY_ALIASES, CATEGORY_ORDER, category_label, normalize_category
from app.core.config import get_settings
from app.core.currencies import SUPPORTED_CURRENCIES, currency_label, normalize_currency
from app.core.types import TransactionType
from app.db.session import SessionLocal
from app.db.models import Transaction, User
from app.services.parser import ParsedTransaction, classify_transaction_text
from app.services.reports import (
    build_period_report,
    last_n_months_range,
    month_range,
    previous_month_range,
    previous_n_months_range,
    previous_week_range,
    previous_year_range,
    week_range,
    year_range,
)
from app.services.smart_parser import parse_transaction_smart
from app.services.transactions import (
    add_transaction,
    delete_transaction,
    delete_all_user_transactions,
    export_transactions,
    get_last_transaction,
    get_transaction_by_id,
    get_or_create_user,
    delete_budget_limit,
    list_budget_limits,
    list_recent_transactions,
    list_transactions_since,
    set_budget_limit,
    spending_by_category,
    total_by_merchant,
    totals_by_category,
    update_user_default_currency,
    update_transaction,
    user_activity_stats,
)

router = Router()
settings = get_settings()

EDIT_PREFIXES = ("измени", "исправь", "поменяй", "замени")
DELETE_PREFIXES = ("удали", "удалить", "сотри", "убери")
INCOME_WORDS = ("доход", "приход", "income", "зарплата")
EXPENSE_WORDS = ("расход", "трата", "expense", "покупка", "потратил", "потратила")
EDIT_TARGET_RE = re.compile(r"^(?:#|id\s+|айди\s+|запись\s+)(\d+)\s*(.*)$", re.I)
EDIT_TARGET_NUMBER_RE = re.compile(r"^(\d+)\s+(?:номер|запись|транзакц(?:ия|ию|ии)?)\s*(?:на\s+)?(.*)$", re.I)
EDIT_TARGET_AMOUNT_RE = re.compile(r"^(\d+)\s+на\s+(.+)$", re.I)
EDIT_TARGET_LABEL_RE = re.compile(r"^(?:номер|запись|транзакц(?:ия|ию|ии)?)\s+#?(\d+)\s*(?:на\s+)?(.*)$", re.I)
TARGET_ID_RE = re.compile(r"(?:#|id\s+|айди\s+|запись\s+#?)(\d+)", re.I)
PENDING_TRANSACTIONS: dict[int, ParsedTransaction] = {}


HELP_TEXT = """Я умею записывать доходы и расходы простыми сообщениями.

Примеры:
300 lidl
получил 500 злотых
вчера 42 biedronka
12.05 такси 18

Команды:
/summary - итоги по категориям
/week - отчет за неделю
/month - отчет за месяц
/year - отчет за год
/limit - месячные лимиты
/currency - валюта по умолчанию
/categories - список категорий
/recent - последние записи с номерами для исправления
/edit - записи за 14 дней для исправления
/myid - показать твой Telegram ID для админ-настроек
/users - админская статистика пользователей
/merchant lidl - сколько потрачено в конкретном магазине
/export - выгрузка в Excel
/help - подсказка
/menu - показать кнопки меню

Меню:
Отчеты - быстрые отчеты за месяц, 3 месяца, полгода, год
Экспорт - выгрузка в Excel
Настройки - валюта, лимиты, категории
Последние - последние записи
Исправить - записи за 14 дней и подсказки

Исправления:
измени росман 30
измени #12 росман 30
исправь на расход
удали последнюю запись
удали #12"""


@router.message(Command("start", "help"))
async def help_handler(message: Message) -> None:
    await message.answer(HELP_TEXT, reply_markup=_main_menu_keyboard())


@router.message(Command("menu"))
async def menu_handler(message: Message) -> None:
    await message.answer("Меню под рукой:", reply_markup=_main_menu_keyboard())


@router.message(Command("myid"))
async def myid_handler(message: Message) -> None:
    await message.answer(f"Твой Telegram ID: {message.from_user.id}")


@router.message(Command("users", "admin_stats"))
async def users_stats_handler(message: Message) -> None:
    if not _is_admin(message.from_user.id):
        await message.answer("Эта команда доступна только админу.")
        return
    await message.answer(await _build_user_activity_text())


@router.message(F.text.in_({"Отчеты", "📊 Отчеты"}))
async def reports_menu_handler(message: Message) -> None:
    await message.answer("Выбери отчет:", reply_markup=_reports_keyboard())


@router.message(F.text.in_({"Экспорт", "📤 Экспорт"}))
async def export_menu_handler(message: Message) -> None:
    await message.answer("За какой период сделать экспорт?", reply_markup=_export_period_keyboard())


@router.message(F.text.in_({"Настройки", "⚙️ Настройки"}))
async def settings_menu_handler(message: Message) -> None:
    await message.answer("Настройки:", reply_markup=_settings_keyboard(_is_admin(message.from_user.id)))


@router.message(F.text.in_({"Помощь", "❓ Помощь"}))
async def help_menu_handler(message: Message) -> None:
    await message.answer(HELP_TEXT, reply_markup=_main_menu_keyboard())


@router.message(F.text.in_({"Категории", "🏷 Категории"}))
async def categories_menu_handler(message: Message) -> None:
    await message.answer(_categories_text())


@router.message(F.text.in_({"Последние", "🧾 Последние"}))
async def recent_menu_handler(message: Message) -> None:
    await _send_recent(message)


@router.message(F.text.in_({"Исправить", "✏️ Исправить"}))
async def edit_menu_handler(message: Message) -> None:
    await _send_editable_transactions(message)


@router.message(Command("categories", "category", "категории"))
async def categories_handler(message: Message) -> None:
    await message.answer(_categories_text())


@router.message(Command("summary"))
async def summary_handler(message: Message) -> None:
    async with SessionLocal() as session:
        user = await get_or_create_user(
            session,
            message.from_user.id,
            message.from_user.username,
            message.from_user.first_name,
        )
        totals = await totals_by_category(session, user)
        await session.commit()

    if not totals:
        await message.answer("Пока нет записей. Напиши что-то вроде: 300 lidl")
        return

    lines = ["Итоги по категориям:"]
    for category, tx_type, currency, total in totals:
        label = "Доход" if tx_type.value == "income" else "Расход"
        lines.append(f"{label}: {category_label(category)} - {total:.2f} {currency}")
    await message.answer("\n".join(lines))


@router.message(Command("month", "report"))
async def month_handler(message: Message) -> None:
    try:
        report_day = _extract_report_month(message.text, datetime.now(settings.tz).date())
    except ValueError as exc:
        await message.answer(str(exc))
        return
    from_date, to_date = month_range(report_day)
    previous_from, previous_to = previous_month_range(report_day)

    async with SessionLocal() as session:
        user = await get_or_create_user(
            session,
            message.from_user.id,
            message.from_user.username,
            message.from_user.first_name,
        )
        report = await build_period_report(
            session,
            user,
            from_date,
            to_date,
            f"Отчет за {from_date.strftime('%m.%Y')}",
            previous_from,
            previous_to,
        )
        await session.commit()

    await message.answer(report)


@router.message(Command("week"))
async def week_handler(message: Message) -> None:
    today = datetime.now(settings.tz).date()
    from_date, to_date = week_range(today)
    previous_from, previous_to = previous_week_range(today)
    async with SessionLocal() as session:
        user = await get_or_create_user(
            session,
            message.from_user.id,
            message.from_user.username,
            message.from_user.first_name,
        )
        report = await build_period_report(session, user, from_date, to_date, "Отчет за неделю", previous_from, previous_to)
        await session.commit()

    await message.answer(report)


@router.message(Command("year"))
async def year_handler(message: Message) -> None:
    today = datetime.now(settings.tz).date()
    from_date, to_date = year_range(today)
    previous_from, previous_to = previous_year_range(today)
    async with SessionLocal() as session:
        user = await get_or_create_user(
            session,
            message.from_user.id,
            message.from_user.username,
            message.from_user.first_name,
        )
        report = await build_period_report(session, user, from_date, to_date, "Отчет за год", previous_from, previous_to)
        await session.commit()

    await message.answer(report)


@router.message(Command("limit", "limits"))
async def limit_handler(message: Message) -> None:
    parts = message.text.split(maxsplit=1)
    today = datetime.now(settings.tz).date()
    async with SessionLocal() as session:
        user = await get_or_create_user(
            session,
            message.from_user.id,
            message.from_user.username,
            message.from_user.first_name,
        )
        if len(parts) == 1:
            answer = await _format_limits(session, user, today)
        else:
            answer = await _handle_limit_command(session, user, parts[1], today)
        await session.commit()

    await message.answer(answer)


@router.message(Command("recent", "last"))
async def recent_handler(message: Message) -> None:
    await _send_recent(message)


@router.message(Command("edit", "change", "исправить"))
async def edit_handler(message: Message) -> None:
    await _send_editable_transactions(message)


async def _send_recent(message: Message, telegram_user=None) -> None:
    telegram_user = telegram_user or message.from_user
    if not telegram_user:
        await message.answer("Не смог определить пользователя.")
        return

    async with SessionLocal() as session:
        user = await get_or_create_user(
            session,
            telegram_user.id,
            telegram_user.username,
            telegram_user.first_name,
        )
        transactions = await list_recent_transactions(session, user)
        await session.commit()

    if not transactions:
        await message.answer("Пока нет записей. Напиши что-то вроде: 300 lidl")
        return

    lines = ["Последние записи:"]
    lines.extend(_format_transaction_line(tx) for tx in transactions)
    lines.append("")
    lines.append("Чтобы исправить конкретную: измени #номер росман 30")
    await message.answer("\n".join(lines))


async def _send_editable_transactions(message: Message, telegram_user=None) -> None:
    telegram_user = telegram_user or message.from_user
    if not telegram_user:
        await message.answer("Не смог определить пользователя.")
        return

    today = datetime.now(settings.tz).date()
    from_date = today - timedelta(days=13)
    async with SessionLocal() as session:
        user = await get_or_create_user(
            session,
            telegram_user.id,
            telegram_user.username,
            telegram_user.first_name,
        )
        transactions = await list_transactions_since(session, user, from_date)
        await session.commit()

    if not transactions:
        await message.answer("За последние 14 дней нет записей для исправления.")
        return

    lines = [f"Записи за последние 14 дней ({from_date.isoformat()} - {today.isoformat()}):"]
    lines.extend(_format_transaction_line(tx) for tx in transactions)
    lines.extend(
        [
            "",
            "Как исправить:",
            "измени #номер на 40",
            "измени #номер категория продукты",
            "измени #номер росман 30",
            "удали #номер",
        ]
    )
    await message.answer("\n".join(lines))


@router.message(Command("merchant"))
async def merchant_handler(message: Message) -> None:
    parts = message.text.split(maxsplit=1)
    if len(parts) < 2:
        await message.answer("Напиши магазин: /merchant lidl")
        return

    merchant = parts[1].strip().lower()
    async with SessionLocal() as session:
        user = await get_or_create_user(
            session,
            message.from_user.id,
            message.from_user.username,
            message.from_user.first_name,
        )
        totals = await total_by_merchant(session, user, merchant)
        await session.commit()

    if not totals:
        await message.answer(f"{merchant}: 0.00 {user.default_currency}")
        return

    lines = [f"{merchant}:"]
    lines.extend(f"{total:.2f} {currency}" for currency, total in totals)
    await message.answer("\n".join(lines))


@router.message(Command("currency", "valuta", "валюта"))
async def currency_handler(message: Message) -> None:
    parts = message.text.split(maxsplit=1)
    async with SessionLocal() as session:
        user = await get_or_create_user(
            session,
            message.from_user.id,
            message.from_user.username,
            message.from_user.first_name,
        )

        if len(parts) == 1:
            await session.commit()
            await message.answer(_currency_settings_text(user.default_currency), reply_markup=_currency_keyboard())
            return

        currency = normalize_currency(parts[1])
        if currency not in SUPPORTED_CURRENCIES:
            await session.commit()
            await message.answer("Не понял валюту. Доступно: PLN, USD, BYN, EUR")
            return

        await update_user_default_currency(session, user, currency)
        await session.commit()

    await message.answer(f"Готово. Валюта по умолчанию: {currency} ({currency_label(currency)})")


@router.callback_query(F.data.startswith("currency:"))
async def currency_callback_handler(callback: CallbackQuery) -> None:
    currency = normalize_currency(callback.data.split(":", maxsplit=1)[1] if callback.data else None)
    if currency not in SUPPORTED_CURRENCIES:
        await callback.answer("Не понял валюту", show_alert=True)
        return

    async with SessionLocal() as session:
        user = await get_or_create_user(
            session,
            callback.from_user.id,
            callback.from_user.username,
            callback.from_user.first_name,
        )
        await update_user_default_currency(session, user, currency)
        await session.commit()

    await callback.answer(f"Выбрано: {currency}")
    if callback.message:
        await callback.message.edit_text(_currency_settings_text(currency), reply_markup=_currency_keyboard())


@router.callback_query(F.data.startswith("report:"))
async def report_callback_handler(callback: CallbackQuery) -> None:
    try:
        from_date, to_date, title, previous_from, previous_to = _report_period_from_callback(callback.data or "")
    except ValueError:
        await callback.answer("Не понял период", show_alert=True)
        return

    async with SessionLocal() as session:
        user = await get_or_create_user(
            session,
            callback.from_user.id,
            callback.from_user.username,
            callback.from_user.first_name,
        )
        report = await build_period_report(session, user, from_date, to_date, title, previous_from, previous_to)
        await session.commit()

    await callback.answer("Готово")
    if callback.message:
        await callback.message.answer(report)


@router.callback_query(F.data.startswith("settings:"))
async def settings_callback_handler(callback: CallbackQuery) -> None:
    action = callback.data.split(":", maxsplit=1)[1] if callback.data else ""
    await callback.answer()
    if not callback.message:
        return
    if action == "currency":
        async with SessionLocal() as session:
            user = await get_or_create_user(
                session,
                callback.from_user.id,
                callback.from_user.username,
                callback.from_user.first_name,
            )
            currency = user.default_currency
            await session.commit()
        await callback.message.answer(_currency_settings_text(currency), reply_markup=_currency_keyboard())
    elif action == "limits":
        async with SessionLocal() as session:
            user = await get_or_create_user(
                session,
                callback.from_user.id,
                callback.from_user.username,
                callback.from_user.first_name,
            )
            answer = await _format_limits(session, user, datetime.now(settings.tz).date())
            await session.commit()
        await callback.message.answer(answer)
    elif action == "categories":
        await callback.message.answer(_categories_text())
    elif action == "recent":
        await _send_recent(callback.message, callback.from_user)
    elif action == "users":
        if not _is_admin(callback.from_user.id):
            await callback.message.answer("Эта настройка доступна только админу.")
            return
        await callback.message.answer(await _build_user_activity_text())
    else:
        await callback.message.answer("Не понял настройку.")


@router.callback_query(F.data.startswith("admin_clear:"))
async def admin_clear_callback_handler(callback: CallbackQuery) -> None:
    if not _is_admin(callback.from_user.id):
        await callback.answer("Эта кнопка доступна только админу", show_alert=True)
        return

    action = callback.data.split(":", maxsplit=1)[1] if callback.data else ""
    if action == "ask":
        await callback.answer()
        if callback.message:
            await callback.message.answer(
                "Удалить все твои записи? Валюта и лимиты останутся.",
                reply_markup=_admin_clear_keyboard(),
            )
        return

    if action == "no":
        await callback.answer("Отменено")
        if callback.message:
            await callback.message.edit_text("Ок, ничего не удаляю.")
        return

    if action != "yes":
        await callback.answer("Не понял действие", show_alert=True)
        return

    async with SessionLocal() as session:
        user = await get_or_create_user(
            session,
            callback.from_user.id,
            callback.from_user.username,
            callback.from_user.first_name,
        )
        deleted = await delete_all_user_transactions(session, user)
        await session.commit()

    await callback.answer("Готово")
    if callback.message:
        await callback.message.edit_text(f"Удалил твои записи: {deleted}. Настройки и лимиты не трогал.")


@router.callback_query(F.data.startswith("tx_confirm:"))
async def transaction_confirm_callback(callback: CallbackQuery) -> None:
    if callback.data == "tx_confirm:no":
        PENDING_TRANSACTIONS.pop(callback.from_user.id, None)
        await callback.answer("Отменено")
        if callback.message:
            await callback.message.edit_text("Ок, не записываю.")
        return

    parsed = PENDING_TRANSACTIONS.pop(callback.from_user.id, None)
    if not parsed:
        await callback.answer("Эта заявка уже неактуальна", show_alert=True)
        return

    async with SessionLocal() as session:
        user = await get_or_create_user(
            session,
            callback.from_user.id,
            callback.from_user.username,
            callback.from_user.first_name,
        )
        tx = await add_transaction(session, user, parsed, "confirmed")
        warning = await _limit_warning(session, user, tx.category, tx.currency, datetime.now(settings.tz).date())
        await session.commit()

    await callback.answer("Записал")
    text = _format_transaction_response("Записал", tx)
    if warning:
        text += f"\n{warning}"
    if callback.message:
        await callback.message.edit_text(text)


@router.callback_query(F.data.startswith("export:"))
async def export_callback_handler(callback: CallbackQuery) -> None:
    try:
        from_date, to_date = _export_period_from_callback(callback.data or "")
    except ValueError:
        await callback.answer("Не понял период", show_alert=True)
        return

    async with SessionLocal() as session:
        user = await get_or_create_user(
            session,
            callback.from_user.id,
            callback.from_user.username,
            callback.from_user.first_name,
        )
        path = await export_transactions(session, user, Path("exports"), from_date, to_date)
        await session.commit()

    await callback.answer("Готовлю Excel")
    if callback.message:
        await callback.message.answer_document(FSInputFile(path), caption=_export_caption(from_date, to_date))


@router.message(Command("export"))
async def export_handler(message: Message) -> None:
    period_text = message.text.split(maxsplit=1)[1] if message.text and len(message.text.split(maxsplit=1)) > 1 else None
    if not period_text:
        await message.answer("За какой период сделать экспорт?", reply_markup=_export_period_keyboard())
        return

    await _send_export(message, period_text)


async def _send_export(message: Message, period_text: str) -> None:
    try:
        from_date, to_date = _parse_export_period(period_text, datetime.now(settings.tz).date())
    except ValueError as exc:
        await message.answer(str(exc))
        return

    async with SessionLocal() as session:
        user = await get_or_create_user(
            session,
            message.from_user.id,
            message.from_user.username,
            message.from_user.first_name,
        )
        path = await export_transactions(session, user, Path("exports"), from_date, to_date)
        await session.commit()

    await message.answer_document(FSInputFile(path), caption=_export_caption(from_date, to_date))


@router.message(Command("delete", "del"))
async def delete_command_handler(message: Message) -> None:
    delete_text = message.text.split(maxsplit=1)[1] if message.text and len(message.text.split(maxsplit=1)) > 1 else ""
    await _delete_transaction_by_text(message, delete_text)


@router.message(F.text)
async def transaction_handler(message: Message) -> None:
    if message.text and message.text.strip().startswith("/"):
        await message.answer("Не знаю такую команду. Напиши /help, чтобы посмотреть доступные команды.")
        return

    today = datetime.now(settings.tz).date()
    export_text = _extract_natural_export_period(message.text)
    if export_text is not None:
        await _send_export(message, export_text)
        return

    delete_text = _extract_delete_text(message.text)
    if delete_text is not None:
        await _delete_transaction_by_text(message, delete_text)
        return

    edit_text = _extract_edit_text(message.text)

    if edit_text is not None:
        if not edit_text:
            await message.answer("Что изменить? Например: измени росман 30 или измени #12 росман 30")
            return

        target_id, edit_text = _extract_edit_target(edit_text)
        if not edit_text:
            await message.answer("Что записать вместо этого? Например: измени #12 росман 30")
            return

        async with SessionLocal() as session:
            user = await get_or_create_user(
                session,
                message.from_user.id,
                message.from_user.username,
                message.from_user.first_name,
            )
            tx_to_edit = (
                await get_transaction_by_id(session, user, target_id)
                if target_id is not None
                else await get_last_transaction(session, user)
            )
            if not tx_to_edit:
                await session.commit()
                if target_id is None:
                    await message.answer("Пока нечего изменять. Сначала добавь запись.")
                else:
                    await message.answer(f"Не нашел твою запись #{target_id}. Посмотри номера через /recent")
                return

            try:
                parsed = _parse_partial_edit(edit_text, tx_to_edit)
            except ValueError:
                try:
                    parsed = await parse_transaction_smart(
                        edit_text,
                        today=today,
                        settings=settings,
                        default_currency=user.default_currency,
                    )
                except ValueError as exc:
                    await session.commit()
                    await message.answer(
                        f"{exc}\n"
                        "Для исправления напиши, например: измени #12 на 40 злотых, измени #12 росман 30 или исправь #12 на расход"
                    )
                    return

            tx = await update_transaction(session, tx_to_edit, parsed, message.text)
            await session.commit()

        await message.answer(_format_transaction_response("Обновил", tx))
        return

    async with SessionLocal() as session:
        user = await get_or_create_user(
            session,
            message.from_user.id,
            message.from_user.username,
            message.from_user.first_name,
        )
        try:
            parsed = await parse_transaction_smart(
                message.text,
                today=today,
                settings=settings,
                default_currency=user.default_currency,
            )
        except ValueError as exc:
            await session.commit()
            await message.answer(str(exc))
            return

        user_category = _extract_user_category(message.text)
        if user_category:
            parsed = _with_category(parsed, user_category)

        if _needs_confirmation(parsed):
            PENDING_TRANSACTIONS[message.from_user.id] = parsed
            await session.commit()
            await message.answer(
                f"Не уверен. Это {_format_parsed_transaction(parsed)}?",
                reply_markup=_confirmation_keyboard(),
            )
            return

        tx = await add_transaction(session, user, parsed, message.text)
        warning = await _limit_warning(session, user, tx.category, tx.currency, today)
        await session.commit()

    answer = _format_transaction_response("Записал", tx)
    if warning:
        answer += f"\n{warning}"
    await message.answer(answer)


async def _delete_transaction_by_text(message: Message, delete_text: str) -> None:
    try:
        target_id = _extract_delete_target(delete_text)
    except ValueError as exc:
        await message.answer(str(exc))
        return

    async with SessionLocal() as session:
        user = await get_or_create_user(
            session,
            message.from_user.id,
            message.from_user.username,
            message.from_user.first_name,
        )
        tx_to_delete = (
            await get_transaction_by_id(session, user, target_id)
            if target_id is not None
            else await get_last_transaction(session, user)
        )

        if not tx_to_delete:
            await session.commit()
            if target_id is None:
                await message.answer("Пока нечего удалять.")
            else:
                await message.answer(f"Не нашел твою запись #{target_id}. Посмотри номера через /recent")
            return

        response = _format_transaction_response("Удалил", tx_to_delete)
        await delete_transaction(session, tx_to_delete)
        await session.commit()

    await message.answer(response)


async def _build_user_activity_text() -> str:
    now = datetime.now(settings.tz)
    async with SessionLocal() as session:
        rows = await user_activity_stats(session, now)
        await session.commit()

    total_users = len(rows)
    users_with_transactions = sum(1 for _, total, _, _, _, _, _ in rows if total > 0)
    active_today = sum(1 for _, _, today, _, _, _, _ in rows if today > 0)
    active_7 = sum(1 for _, _, _, last_7, _, _, _ in rows if last_7 > 0)
    active_30 = sum(1 for _, _, _, _, last_30, _, _ in rows if last_30 > 0)
    today_transactions = sum(today for _, _, today, _, _, _, _ in rows)
    total_transactions = sum(total for _, total, _, _, _, _, _ in rows)

    lines = [
        "Статистика пользователей:",
        f"Всего пользователей: {total_users}",
        f"С записями: {users_with_transactions}",
        f"Активны сегодня: {active_today}",
        f"Записей сегодня: {today_transactions}",
        f"Активны за 7 дней: {active_7}",
        f"Активны за 30 дней: {active_30}",
        f"Всего записей: {total_transactions}",
    ]

    if not rows:
        return "\n".join(lines)

    lines.extend(["", "Последняя активность:"])
    for user, total, today, last_7, last_30, last_tx_created_at, last_tx_date in rows[:15]:
        name = _format_user_name(user)
        last_seen = _format_datetime(last_tx_created_at)
        tx_date = last_tx_date.isoformat() if last_tx_date else "-"
        lines.append(
            f"{name}: {total} записей, сегодня: {today}, 7д: {last_7}, 30д: {last_30}, "
            f"последняя: {last_seen}, дата записи: {tx_date}"
        )

    if len(rows) > 15:
        lines.append(f"...и еще {len(rows) - 15}")
    return "\n".join(lines)


def _format_user_name(user: User) -> str:
    name = user.first_name or user.username or str(user.telegram_id)
    if user.username:
        return f"{name} (@{user.username}, {user.telegram_id})"
    return f"{name} ({user.telegram_id})"


def _format_datetime(value: datetime | None) -> str:
    if not value:
        return "-"
    if value.tzinfo:
        value = value.astimezone(settings.tz)
    return value.strftime("%Y-%m-%d %H:%M")


def _extract_edit_text(text: str | None) -> str | None:
    if not text:
        return None

    normalized = text.strip().lower()
    for prefix in EDIT_PREFIXES:
        if normalized == prefix:
            return ""
        if normalized.startswith(f"{prefix} "):
            return text.strip()[len(prefix) :].strip()
    return None


def _is_admin(telegram_id: int | None) -> bool:
    if telegram_id is None:
        return False
    return telegram_id in _admin_ids()


def _admin_ids() -> set[int]:
    ids = set()
    for raw_id in settings.admin_telegram_ids.split(","):
        raw_id = raw_id.strip()
        if not raw_id:
            continue
        try:
            ids.add(int(raw_id))
        except ValueError:
            continue
    return ids


def _currency_keyboard() -> InlineKeyboardMarkup:
    return InlineKeyboardMarkup(
        inline_keyboard=[
            [
                InlineKeyboardButton(text=f"{currency} - {currency_label(currency)}", callback_data=f"currency:{currency}")
            ]
            for currency in SUPPORTED_CURRENCIES
        ]
    )


def _main_menu_keyboard() -> ReplyKeyboardMarkup:
    return ReplyKeyboardMarkup(
        keyboard=[
            [KeyboardButton(text="📊 Отчеты"), KeyboardButton(text="📤 Экспорт")],
            [KeyboardButton(text="✏️ Исправить"), KeyboardButton(text="🧾 Последние")],
            [KeyboardButton(text="⚙️ Настройки"), KeyboardButton(text="🏷 Категории")],
            [KeyboardButton(text="❓ Помощь")],
        ],
        resize_keyboard=True,
        input_field_placeholder="Напиши расход: 300 lidl",
    )


def _reports_keyboard() -> InlineKeyboardMarkup:
    return InlineKeyboardMarkup(
        inline_keyboard=[
            [
                InlineKeyboardButton(text="Текущий месяц", callback_data="report:month"),
                InlineKeyboardButton(text="3 месяца", callback_data="report:3_months"),
            ],
            [
                InlineKeyboardButton(text="Полгода", callback_data="report:6_months"),
                InlineKeyboardButton(text="Год", callback_data="report:year"),
            ],
            [
                InlineKeyboardButton(text="Неделя", callback_data="report:week"),
                InlineKeyboardButton(text="Прошлый месяц", callback_data="report:last_month"),
            ],
        ]
    )


def _settings_keyboard(is_admin: bool = False) -> InlineKeyboardMarkup:
    keyboard = [
        [
            InlineKeyboardButton(text="Валюта", callback_data="settings:currency"),
            InlineKeyboardButton(text="Лимиты", callback_data="settings:limits"),
        ],
        [
            InlineKeyboardButton(text="Категории", callback_data="settings:categories"),
            InlineKeyboardButton(text="Последние записи", callback_data="settings:recent"),
        ],
    ]
    if is_admin:
        keyboard.append([InlineKeyboardButton(text="Статистика пользователей", callback_data="settings:users")])
        keyboard.append([InlineKeyboardButton(text="Очистить мои записи", callback_data="admin_clear:ask")])
    return InlineKeyboardMarkup(inline_keyboard=keyboard)


def _admin_clear_keyboard() -> InlineKeyboardMarkup:
    return InlineKeyboardMarkup(
        inline_keyboard=[
            [
                InlineKeyboardButton(text="Да, удалить мои записи", callback_data="admin_clear:yes"),
                InlineKeyboardButton(text="Отмена", callback_data="admin_clear:no"),
            ]
        ]
    )


def _report_period_from_callback(data: str) -> tuple[date, date, str, date | None, date | None]:
    today = datetime.now(settings.tz).date()
    period = data.split(":", maxsplit=1)[1]
    if period == "week":
        from_date, to_date = week_range(today)
        previous_from, previous_to = previous_week_range(today)
        return from_date, to_date, "Отчет за неделю", previous_from, previous_to
    if period == "month":
        from_date, to_date = month_range(today)
        previous_from, previous_to = previous_month_range(today)
        return from_date, to_date, f"Отчет за {from_date.strftime('%m.%Y')}", previous_from, previous_to
    if period == "last_month":
        from_date, to_date = previous_month_range(today)
        previous_from, previous_to = previous_month_range(from_date)
        return from_date, to_date, f"Отчет за {from_date.strftime('%m.%Y')}", previous_from, previous_to
    if period == "3_months":
        from_date, to_date = last_n_months_range(today, 3)
        previous_from, previous_to = previous_n_months_range(today, 3)
        return from_date, to_date, "Отчет за 3 месяца", previous_from, previous_to
    if period == "6_months":
        from_date, to_date = last_n_months_range(today, 6)
        previous_from, previous_to = previous_n_months_range(today, 6)
        return from_date, to_date, "Отчет за полгода", previous_from, previous_to
    if period == "year":
        from_date, to_date = year_range(today)
        previous_from, previous_to = previous_year_range(today)
        return from_date, to_date, "Отчет за год", previous_from, previous_to
    raise ValueError("Unknown report period")


def _categories_text() -> str:
    lines = [
        "Категории:",
        f"{category_label('income')} - зарплата, доход, перевод",
    ]
    for category in CATEGORY_ORDER:
        aliases = ", ".join(CATEGORY_ALIASES.get(category, ())[:4])
        if aliases:
            lines.append(f"{category_label(category)} - {aliases}")
        else:
            lines.append(category_label(category))

    lines.extend(
        [
            "",
            "Можно указать категорию прямо в сообщении:",
            "56 евроопт категория продукты",
            "стоматолог 180 категория здоровье",
        ]
    )
    return "\n".join(lines)


def _currency_settings_text(currency: str) -> str:
    return (
        f"Текущая валюта по умолчанию: {currency} ({currency_label(currency)}).\n"
        "Выбери новую валюту кнопкой или напиши: /currency PLN, /currency USD, /currency BYN, /currency EUR"
    )


def _export_period_keyboard() -> InlineKeyboardMarkup:
    return InlineKeyboardMarkup(
        inline_keyboard=[
            [
                InlineKeyboardButton(text="Этот месяц", callback_data="export:month"),
                InlineKeyboardButton(text="Прошлый месяц", callback_data="export:last_month"),
            ],
            [
                InlineKeyboardButton(text="3 месяца", callback_data="export:3_months"),
                InlineKeyboardButton(text="Полгода", callback_data="export:6_months"),
            ],
            [
                InlineKeyboardButton(text="Эта неделя", callback_data="export:week"),
            ],
            [
                InlineKeyboardButton(text="Этот год", callback_data="export:year"),
                InlineKeyboardButton(text="Прошлый год", callback_data="export:last_year"),
            ],
            [
                InlineKeyboardButton(text="Все время", callback_data="export:all"),
            ],
        ]
    )


def _export_period_from_callback(data: str) -> tuple[date | None, date | None]:
    today = datetime.now(settings.tz).date()
    period = data.split(":", maxsplit=1)[1]
    if period == "week":
        return week_range(today)
    if period == "month":
        return month_range(today)
    if period == "last_month":
        return previous_month_range(today)
    if period == "3_months":
        return last_n_months_range(today, 3)
    if period == "6_months":
        return last_n_months_range(today, 6)
    if period == "year":
        return year_range(today)
    if period == "last_year":
        previous = today.replace(year=today.year - 1)
        return year_range(previous)
    if period == "all":
        return None, None
    raise ValueError("Unknown export period")


def _parse_export_period(text: str, today: date) -> tuple[date | None, date | None]:
    normalized = text.strip().lower()
    normalized = re.sub(r"\s+", " ", normalized)
    normalized = re.sub(r"^за\s+последн(?:ие|их|ий|юю)\s+", "за ", normalized)
    normalized = re.sub(r"^последн(?:ие|их|ий|юю)\s+", "", normalized)
    if normalized in {"all", "все", "всё", "все время", "всё время", "за все время", "за всё время"}:
        return None, None
    if normalized in {"week", "неделя", "эта неделя", "за неделю", "текущая неделя"}:
        return week_range(today)
    if normalized in {"month", "месяц", "этот месяц", "за месяц", "текущий месяц"}:
        return month_range(today)
    if normalized in {"last month", "прошлый месяц", "предыдущий месяц"}:
        return previous_month_range(today)
    if normalized in {"year", "год", "за год", "этот год", "текущий год"}:
        return year_range(today)
    if normalized in {"last year", "прошлый год", "предыдущий год"}:
        return year_range(today.replace(year=today.year - 1))
    if normalized in {"полгода", "пол года", "за полгода", "за пол года", "half year"}:
        return last_n_months_range(today, 6)

    months_match = re.fullmatch(r"(?:за\s+)?(\d{1,2})\s*(?:месяц|месяца|месяцев|мес|months?)", normalized)
    if months_match:
        months = int(months_match.group(1))
        if months < 1:
            raise ValueError("Количество месяцев должно быть больше 0.")
        return last_n_months_range(today, months)

    parts = normalized.split()
    if len(parts) == 1:
        month = _extract_report_month(f"/export {parts[0]}", today)
        return month_range(month)
    if len(parts) == 2:
        try:
            return date.fromisoformat(parts[0]), date.fromisoformat(parts[1])
        except ValueError as exc:
            raise ValueError("Не понял период. Пример: /export 2026-05-01 2026-05-31") from exc

    raise ValueError("Не понял период. Напиши /export month, /export 2026-05 или /export 2026-05-01 2026-05-31")


def _extract_natural_export_period(text: str | None) -> str | None:
    if not text:
        return None

    normalized = re.sub(r"\s+", " ", text.strip().lower())
    if not re.search(r"\b(экспорт|выгрузк[ауи]?|excel|ексель)\b", normalized):
        return None

    cleaned = re.sub(r"^(?:дай|сделай|сформируй|подготовь|пришли|скинь|выгрузи)\s+(?:мне\s+)?", "", normalized)
    cleaned = re.sub(r"\b(?:экспорт|выгрузк[ауи]?|excel|ексель)\b", "", cleaned).strip()
    cleaned = re.sub(r"^(?:данных|транзакций|операций)\s*", "", cleaned).strip()
    cleaned = re.sub(r"^(?:за|на)\s+", "за ", cleaned).strip()
    return cleaned or "all"


def _export_caption(from_date: date | None, to_date: date | None) -> str:
    if from_date and to_date:
        return f"Готово, Excel за период {from_date.isoformat()} - {to_date.isoformat()}."
    return "Готово, Excel за все время."


def _confirmation_keyboard() -> InlineKeyboardMarkup:
    return InlineKeyboardMarkup(
        inline_keyboard=[
            [
                InlineKeyboardButton(text="Да, записать", callback_data="tx_confirm:yes"),
                InlineKeyboardButton(text="Нет", callback_data="tx_confirm:no"),
            ]
        ]
    )


def _needs_confirmation(parsed: ParsedTransaction) -> bool:
    return parsed.amount <= 0 or parsed.category == "other"


def _format_parsed_transaction(parsed: ParsedTransaction) -> str:
    direction = "доход" if parsed.type.value == "income" else "расход"
    merchant = f", метка: {parsed.merchant}" if parsed.merchant else ""
    return (
        f"{direction}: {parsed.amount:.2f} {parsed.currency}, "
        f"категория: {category_label(parsed.category)}{merchant}, дата: {parsed.occurred_on.isoformat()}"
    )


def _extract_user_category(text: str | None) -> str | None:
    if not text:
        return None

    match = re.search(r"(?:категория|категорию|как)\s+([а-яёa-z_ ]+)$", text.strip(), re.I)
    if not match:
        return None
    return normalize_category(match.group(1))


def _with_category(parsed: ParsedTransaction, category: str) -> ParsedTransaction:
    tx_type = TransactionType.income if category == "income" else parsed.type
    return ParsedTransaction(
        amount=parsed.amount,
        type=tx_type,
        category=category,
        merchant=parsed.merchant,
        occurred_on=parsed.occurred_on,
        note=parsed.note,
        currency=parsed.currency,
    )


def _extract_delete_text(text: str | None) -> str | None:
    if not text:
        return None

    normalized = text.strip().lower()
    for prefix in DELETE_PREFIXES:
        if normalized == prefix:
            return ""
        if normalized.startswith(f"{prefix} "):
            return text.strip()[len(prefix) :].strip()
    return None


def _extract_delete_target(text: str) -> int | None:
    normalized = text.strip().lower()
    if not normalized or "послед" in normalized or normalized == "last":
        return None

    match = TARGET_ID_RE.search(normalized)
    if match:
        return int(match.group(1))

    raise ValueError("Что удалить? Напиши: удали последнюю запись или удали #12")


def _extract_report_month(text: str | None, today: date) -> date:
    parts = (text or "").split(maxsplit=1)
    if len(parts) == 1:
        return today

    value = parts[1].strip()
    match = re.fullmatch(r"(20\d{2})-(\d{1,2})", value)
    if match:
        year, month = map(int, match.groups())
        return date(year, month, 1)

    match = re.fullmatch(r"(\d{1,2})[./](20\d{2})", value)
    if match:
        month, year = map(int, match.groups())
        return date(year, month, 1)

    raise ValueError("Не понял месяц. Напиши /month, /month 2026-05 или /month 05.2026")


def _extract_edit_target(text: str) -> tuple[int | None, str]:
    cleaned = text.strip()
    for pattern in (EDIT_TARGET_NUMBER_RE, EDIT_TARGET_AMOUNT_RE, EDIT_TARGET_LABEL_RE, EDIT_TARGET_RE):
        match = pattern.match(cleaned)
        if match:
            return int(match.group(1)), _strip_edit_connector(match.group(2))

    return None, _strip_edit_connector(cleaned)


def _strip_edit_connector(text: str) -> str:
    return re.sub(r"^(?:на|в)\s+", "", text.strip(), flags=re.I)


def _parse_partial_edit(text: str, transaction: Transaction) -> ParsedTransaction:
    normalized = _strip_edit_connector(text).lower()
    tx_type, category, merchant = classify_transaction_text(normalized)
    amount_match = re.fullmatch(
        r"(\d+(?:[.,]\d{1,2})?)\s*"
        r"(zł|zl|pln|зл|злот(?:ый|ых|ые|ого)?|\$|usd|доллар(?:а|ов)?|бакс(?:а|ов)?|"
        r"byn|br|бел\.?\s*руб|белруб|рб\s*руб(?:ль|лей)?|руб(?:ль|ля|лей)?|eur|€|евро)?",
        normalized,
        flags=re.I,
    )
    if amount_match:
        currency = normalize_currency(amount_match.group(2)) or transaction.currency
        return ParsedTransaction(
            amount=Decimal(amount_match.group(1).replace(",", ".")),
            type=transaction.type,
            category=transaction.category,
            merchant=transaction.merchant,
            occurred_on=transaction.occurred_on,
            note=transaction.note,
            currency=currency,
        )

    if merchant or category != "other":
        return ParsedTransaction(
            amount=transaction.amount,
            type=tx_type,
            category=category,
            merchant=merchant or transaction.merchant,
            occurred_on=transaction.occurred_on,
            note=merchant or transaction.note,
            currency=transaction.currency,
        )

    if any(word in normalized for word in INCOME_WORDS):
        tx_type = TransactionType.income
        category = "income"
    elif any(word in normalized for word in EXPENSE_WORDS):
        tx_type = TransactionType.expense
        category = "other" if transaction.category == "income" else transaction.category
    else:
        raise ValueError("Не смог прочитать исправление.")

    return ParsedTransaction(
        amount=transaction.amount,
        type=tx_type,
        category=category,
        merchant=transaction.merchant,
        occurred_on=transaction.occurred_on,
        note=transaction.note,
        currency=transaction.currency,
    )


async def _handle_limit_command(session, user: User, text: str, today: date) -> str:
    normalized = text.strip()
    if normalized.lower().startswith(("удали ", "удалить ", "remove ", "delete ")):
        category_text = normalized.split(maxsplit=1)[1]
        category = normalize_category(category_text)
        if not category:
            return "Не понял категорию лимита. Например: /limit продукты 800"
        await delete_budget_limit(session, user, category, user.default_currency)
        return f"Удалил лимит: {category_label(category)} {user.default_currency}"

    parts = normalized.rsplit(maxsplit=2)
    if len(parts) < 2:
        return "Напиши лимит так: /limit продукты 800 или /limit такси 200"

    currency = user.default_currency
    if len(parts) == 3 and normalize_currency(parts[2]):
        category_text, amount_text, currency = parts[0], parts[1], normalize_currency(parts[2])
    else:
        category_text, amount_text = normalized.rsplit(maxsplit=1)

    category = normalize_category(category_text)
    if not category or category == "income":
        return "Не понял категорию. Например: продукты, авто, транспорт, кафе, уход, дом"

    try:
        amount = Decimal(amount_text.replace(",", "."))
    except (InvalidOperation, ValueError):
        return "Не понял сумму лимита. Например: /limit продукты 800"

    await set_budget_limit(session, user, category, amount, currency)
    spent = await spending_by_category(session, user, category, currency, *month_range(today))
    return (
        f"Лимит на месяц: {category_label(category)} {amount:.2f} {currency}.\n"
        f"Уже потрачено: {spent:.2f} {currency}"
    )


async def _format_limits(session, user: User, today: date) -> str:
    limits = await list_budget_limits(session, user)
    if not limits:
        return "Лимитов пока нет. Добавь так: /limit продукты 800"

    from_date, to_date = month_range(today)
    lines = [f"Лимиты на {from_date.strftime('%m.%Y')}:"]
    for limit in limits:
        spent = await spending_by_category(session, user, limit.category, limit.currency, from_date, to_date)
        left = Decimal(limit.amount) - spent
        lines.append(
            f"{category_label(limit.category)}: {spent:.2f} / {limit.amount:.2f} {limit.currency}, осталось {left:.2f}"
        )
    return "\n".join(lines)


async def _limit_warning(session, user: User, category: str, currency: str, today: date) -> str | None:
    limits = await list_budget_limits(session, user)
    limit = next((item for item in limits if item.category == category and item.currency == currency), None)
    if not limit:
        return None

    spent = await spending_by_category(session, user, category, currency, *month_range(today))
    amount = Decimal(limit.amount)
    if spent >= amount:
        return f"Лимит превышен: {category_label(category)} {spent:.2f} / {amount:.2f} {currency}"
    if spent >= amount * Decimal("0.8"):
        return f"Лимит близко: {category_label(category)} {spent:.2f} / {amount:.2f} {currency}"
    return None


def _format_transaction_response(action: str, tx: Transaction) -> str:
    direction = "доход" if tx.type.value == "income" else "расход"
    merchant = f", метка: {tx.merchant}" if tx.merchant else ""
    return (
        f"{action} #{_transaction_number(tx)} {direction}: {tx.amount:.2f} {tx.currency}, "
        f"категория: {category_label(tx.category)}{merchant}, дата: {tx.occurred_on.isoformat()}"
    )


def _format_transaction_line(tx: Transaction) -> str:
    direction = "доход" if tx.type.value == "income" else "расход"
    merchant = f", {tx.merchant}" if tx.merchant else ""
    return (
        f"#{_transaction_number(tx)} {tx.occurred_on.isoformat()} - {direction}: "
        f"{tx.amount:.2f} {tx.currency}, {category_label(tx.category)}{merchant}"
    )


def _transaction_number(tx: Transaction) -> int:
    return tx.user_tx_number or tx.id
