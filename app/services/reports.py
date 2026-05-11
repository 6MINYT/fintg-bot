from calendar import monthrange
from datetime import date, timedelta
from decimal import Decimal

from sqlalchemy.ext.asyncio import AsyncSession

from app.core.categories import CATEGORY_ORDER, category_label
from app.core.types import TransactionType
from app.db.models import User
from app.services.transactions import top_merchants, totals_by_category


def week_range(day: date) -> tuple[date, date]:
    start = day - timedelta(days=day.weekday())
    return start, start + timedelta(days=6)


def month_range(day: date) -> tuple[date, date]:
    last_day = monthrange(day.year, day.month)[1]
    return date(day.year, day.month, 1), date(day.year, day.month, last_day)


def last_n_months_range(day: date, months: int) -> tuple[date, date]:
    month_index = day.year * 12 + day.month - months
    year = month_index // 12
    month = month_index % 12 + 1
    return date(year, month, 1), day


def year_range(day: date) -> tuple[date, date]:
    return date(day.year, 1, 1), date(day.year, 12, 31)


async def build_period_report(
    session: AsyncSession,
    user: User,
    from_date: date,
    to_date: date,
    title: str,
    previous_from: date | None = None,
    previous_to: date | None = None,
) -> str:
    totals = await totals_by_category(session, user, from_date, to_date)
    previous_totals = await totals_by_category(session, user, previous_from, previous_to) if previous_from and previous_to else []
    merchants = await top_merchants(session, user, from_date, to_date)

    income_totals: dict[str, Decimal] = {}
    expense_totals: dict[tuple[str, str], Decimal] = {}
    previous_expense_totals: dict[tuple[str, str], Decimal] = {}

    for category, tx_type, currency, total in totals:
        if tx_type == TransactionType.income:
            income_totals[currency] = income_totals.get(currency, Decimal("0")) + total
        else:
            expense_totals[(category, currency)] = total

    for category, tx_type, currency, total in previous_totals:
        if tx_type == TransactionType.expense:
            previous_expense_totals[(category, currency)] = total

    expense_by_currency: dict[str, Decimal] = {}
    for (_, currency), total in expense_totals.items():
        expense_by_currency[currency] = expense_by_currency.get(currency, Decimal("0")) + total

    currencies = sorted(set(income_totals) | set(expense_by_currency))
    if not currencies:
        return f"{title}\nПока нет записей за период."

    lines = [title, f"Период: {from_date.isoformat()} - {to_date.isoformat()}"]
    for currency in currencies:
        income = income_totals.get(currency, Decimal("0"))
        expense = expense_by_currency.get(currency, Decimal("0"))
        lines.extend(
            [
                f"Доходы: {income:.2f} {currency}",
                f"Расходы: {expense:.2f} {currency}",
                f"Баланс: {(income - expense):.2f} {currency}",
            ]
        )

    biggest = sorted(expense_totals.items(), key=lambda item: item[1], reverse=True)[:3]
    if biggest:
        lines.extend(["", "Куда ушло больше всего:"])
        for (category, currency), total in biggest:
            lines.append(f"{category_label(category)}: {total:.2f} {currency}")

    if merchants:
        lines.extend(["", "Топ магазинов:"])
        for merchant, currency, total in merchants:
            lines.append(f"{merchant}: {total:.2f} {currency}")

    anomalies = _build_anomalies(expense_totals, previous_expense_totals)
    if anomalies:
        lines.extend(["", "Аномалии:"])
        lines.extend(anomalies)

    lines.extend(["", "По категориям:"])
    for category in CATEGORY_ORDER:
        for currency in currencies:
            total = expense_totals.get((category, currency), Decimal("0"))
            if total:
                lines.append(f"{category_label(category)}: {total:.2f} {currency}")

    return "\n".join(lines)


def previous_month_range(day: date) -> tuple[date, date]:
    year = day.year if day.month > 1 else day.year - 1
    month = day.month - 1 if day.month > 1 else 12
    last_day = monthrange(year, month)[1]
    return date(year, month, 1), date(year, month, last_day)


def previous_n_months_range(day: date, months: int) -> tuple[date, date]:
    current_from, _ = last_n_months_range(day, months)
    previous_to = current_from - timedelta(days=1)
    return last_n_months_range(previous_to, months)


def previous_year_range(day: date) -> tuple[date, date]:
    return date(day.year - 1, 1, 1), date(day.year - 1, 12, 31)


def previous_week_range(day: date) -> tuple[date, date]:
    current_from, _ = week_range(day)
    previous_to = current_from - timedelta(days=1)
    previous_from = previous_to - timedelta(days=6)
    return previous_from, previous_to


def _build_anomalies(
    current: dict[tuple[str, str], Decimal],
    previous: dict[tuple[str, str], Decimal],
) -> list[str]:
    lines = []
    for key, current_total in sorted(current.items(), key=lambda item: item[1], reverse=True):
        previous_total = previous.get(key, Decimal("0"))
        if previous_total <= 0 or current_total < previous_total * Decimal("2"):
            continue
        category, currency = key
        ratio = current_total / previous_total
        lines.append(
            f"{category_label(category)}: {current_total:.2f} {currency}, было {previous_total:.2f} {currency} ({ratio:.1f}x)"
        )
    return lines[:3]
