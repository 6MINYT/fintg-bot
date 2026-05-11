import calendar
from datetime import date
from decimal import Decimal

from sqlalchemy.ext.asyncio import AsyncSession

from app.core.categories import CATEGORY_LABELS, CATEGORY_ORDER, category_label
from app.core.types import TransactionType
from app.db.models import User
from app.services.transactions import totals_by_category


def month_range(day: date) -> tuple[date, date]:
    last_day = calendar.monthrange(day.year, day.month)[1]
    return date(day.year, day.month, 1), date(day.year, day.month, last_day)


async def build_monthly_report(session: AsyncSession, user: User, day: date) -> str:
    from_date, to_date = month_range(day)
    totals = await totals_by_category(session, user, from_date, to_date)

    income_totals: dict[str, Decimal] = {}
    expense_totals: dict[tuple[str, str], Decimal] = {}

    for category, tx_type, currency, total in totals:
        if tx_type == TransactionType.income:
            income_totals[currency] = income_totals.get(currency, Decimal("0")) + total
        else:
            key = (category, currency)
            expense_totals[key] = expense_totals.get(key, Decimal("0")) + total

    expense_totals_by_currency: dict[str, Decimal] = {}
    for (_, currency), total in expense_totals.items():
        expense_totals_by_currency[currency] = expense_totals_by_currency.get(currency, Decimal("0")) + total

    currencies = sorted(set(income_totals) | set(expense_totals_by_currency))
    title = f"Отчет за {from_date.strftime('%m.%Y')}"

    if not currencies:
        return f"{title}\nПока нет записей за этот месяц."

    lines = [title]
    for currency in currencies:
        income_total = income_totals.get(currency, Decimal("0"))
        expense_total = expense_totals_by_currency.get(currency, Decimal("0"))
        lines.extend(
            [
                f"Доходы: {income_total:.2f} {currency}",
                f"Расходы: {expense_total:.2f} {currency}",
                f"Баланс: {(income_total - expense_total):.2f} {currency}",
            ]
        )

    lines.extend(["", "Основные траты:"])

    for category in CATEGORY_ORDER:
        for currency in currencies:
            total = expense_totals.pop((category, currency), Decimal("0"))
            if total:
                lines.append(f"{CATEGORY_LABELS[category]}: {total:.2f} {currency}")

    for (category, currency), total in sorted(expense_totals.items()):
        lines.append(f"{category_label(category)}: {total:.2f} {currency}")

    return "\n".join(lines)
