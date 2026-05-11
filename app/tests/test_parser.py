from datetime import date
from decimal import Decimal
from unittest import TestCase

from app.core.types import TransactionType
from app.services.parser import parse_transaction


TODAY = date(2026, 5, 11)


class ParserTest(TestCase):
    def test_income_message(self) -> None:
        parsed = parse_transaction("получил 500 злотых", TODAY)

        self.assertEqual(parsed.amount, Decimal("500"))
        self.assertEqual(parsed.type, TransactionType.income)
        self.assertEqual(parsed.category, "income")
        self.assertEqual(parsed.occurred_on, TODAY)

    def test_lidl_expense_is_groceries_with_merchant(self) -> None:
        parsed = parse_transaction("300 lidl", TODAY)

        self.assertEqual(parsed.amount, Decimal("300"))
        self.assertEqual(parsed.type, TransactionType.expense)
        self.assertEqual(parsed.category, "groceries")
        self.assertEqual(parsed.merchant, "lidl")

    def test_carrefour_cyrillic_typo_is_groceries(self) -> None:
        parsed = parse_transaction("60 коррефур", TODAY)

        self.assertEqual(parsed.amount, Decimal("60"))
        self.assertEqual(parsed.type, TransactionType.expense)
        self.assertEqual(parsed.category, "groceries")
        self.assertEqual(parsed.merchant, "carrefour")

    def test_aldi_cyrillic_typo_is_groceries(self) -> None:
        parsed = parse_transaction("алди 50", TODAY)

        self.assertEqual(parsed.amount, Decimal("50"))
        self.assertEqual(parsed.type, TransactionType.expense)
        self.assertEqual(parsed.category, "groceries")
        self.assertEqual(parsed.merchant, "aldi")

    def test_default_currency_can_be_changed(self) -> None:
        parsed = parse_transaction("300 lidl", TODAY, default_currency="BYN")

        self.assertEqual(parsed.amount, Decimal("300"))
        self.assertEqual(parsed.currency, "BYN")

    def test_explicit_currency_overrides_default(self) -> None:
        parsed = parse_transaction("300 usd lidl", TODAY, default_currency="BYN")

        self.assertEqual(parsed.amount, Decimal("300"))
        self.assertEqual(parsed.currency, "USD")

    def test_rossmann_typo_is_expense_with_merchant(self) -> None:
        parsed = parse_transaction("росман 30", TODAY)

        self.assertEqual(parsed.amount, Decimal("30"))
        self.assertEqual(parsed.type, TransactionType.expense)
        self.assertEqual(parsed.category, "personal_care")
        self.assertEqual(parsed.merchant, "rossmann")

    def test_belarus_grocery_store(self) -> None:
        parsed = parse_transaction("евроопт 65", TODAY)

        self.assertEqual(parsed.amount, Decimal("65"))
        self.assertEqual(parsed.type, TransactionType.expense)
        self.assertEqual(parsed.category, "groceries")
        self.assertEqual(parsed.merchant, "euroopt")

    def test_euroopt_after_amount_is_not_eur_currency(self) -> None:
        parsed = parse_transaction("5 апреля 60 евроопт", TODAY, default_currency="PLN")

        self.assertEqual(parsed.amount, Decimal("60"))
        self.assertEqual(parsed.currency, "PLN")
        self.assertEqual(parsed.category, "groceries")
        self.assertEqual(parsed.merchant, "euroopt")

    def test_euro_currency_still_works_as_word(self) -> None:
        parsed = parse_transaction("кафе 60 евро", TODAY, default_currency="PLN")

        self.assertEqual(parsed.amount, Decimal("60"))
        self.assertEqual(parsed.currency, "EUR")
        self.assertEqual(parsed.category, "cafes")

    def test_euroopt_typo_is_groceries(self) -> None:
        parsed = parse_transaction("еврорт 56", TODAY)

        self.assertEqual(parsed.amount, Decimal("56"))
        self.assertEqual(parsed.type, TransactionType.expense)
        self.assertEqual(parsed.category, "groceries")
        self.assertEqual(parsed.merchant, "euroopt")

    def test_polish_drugstore(self) -> None:
        parsed = parse_transaction("hebe 42", TODAY)

        self.assertEqual(parsed.amount, Decimal("42"))
        self.assertEqual(parsed.type, TransactionType.expense)
        self.assertEqual(parsed.category, "personal_care")
        self.assertEqual(parsed.merchant, "hebe")

    def test_polish_marketplace_is_shopping(self) -> None:
        parsed = parse_transaction("allegro 120", TODAY)

        self.assertEqual(parsed.amount, Decimal("120"))
        self.assertEqual(parsed.type, TransactionType.expense)
        self.assertEqual(parsed.category, "shopping")
        self.assertEqual(parsed.merchant, "allegro")

    def test_belarus_online_store_is_shopping(self) -> None:
        parsed = parse_transaction("21 век 300", TODAY)

        self.assertEqual(parsed.amount, Decimal("300"))
        self.assertEqual(parsed.type, TransactionType.expense)
        self.assertEqual(parsed.category, "shopping")
        self.assertEqual(parsed.merchant, "21vek")

    def test_numeric_store_name_does_not_become_amount(self) -> None:
        parsed = parse_transaction("5 элемент 400", TODAY)

        self.assertEqual(parsed.amount, Decimal("400"))
        self.assertEqual(parsed.type, TransactionType.expense)
        self.assertEqual(parsed.category, "shopping")
        self.assertEqual(parsed.merchant, "5 element")

    def test_pharmacy_chain_is_health(self) -> None:
        parsed = parse_transaction("dr max 45", TODAY)

        self.assertEqual(parsed.amount, Decimal("45"))
        self.assertEqual(parsed.type, TransactionType.expense)
        self.assertEqual(parsed.category, "health")
        self.assertEqual(parsed.merchant, "dr.max")

    def test_sport_store_is_sport(self) -> None:
        parsed = parse_transaction("decathlon 180", TODAY)

        self.assertEqual(parsed.amount, Decimal("180"))
        self.assertEqual(parsed.type, TransactionType.expense)
        self.assertEqual(parsed.category, "sport")
        self.assertEqual(parsed.merchant, "decathlon")

    def test_minsk_grocery_store_is_groceries(self) -> None:
        parsed = parse_transaction("простор 80", TODAY)

        self.assertEqual(parsed.amount, Decimal("80"))
        self.assertEqual(parsed.type, TransactionType.expense)
        self.assertEqual(parsed.category, "groceries")
        self.assertEqual(parsed.merchant, "prostore")

    def test_taxi_store(self) -> None:
        parsed = parse_transaction("bolt 19", TODAY)

        self.assertEqual(parsed.amount, Decimal("19"))
        self.assertEqual(parsed.type, TransactionType.expense)
        self.assertEqual(parsed.category, "transport")
        self.assertEqual(parsed.merchant, "bolt")

    def test_food_delivery_merchant(self) -> None:
        parsed = parse_transaction("wolt 54", TODAY)

        self.assertEqual(parsed.amount, Decimal("54"))
        self.assertEqual(parsed.type, TransactionType.expense)
        self.assertEqual(parsed.category, "delivery")
        self.assertEqual(parsed.merchant, "wolt")

    def test_food_delivery_phrase(self) -> None:
        parsed = parse_transaction("доставка еды 44", TODAY)

        self.assertEqual(parsed.amount, Decimal("44"))
        self.assertEqual(parsed.type, TransactionType.expense)
        self.assertEqual(parsed.category, "delivery")

    def test_home_store(self) -> None:
        parsed = parse_transaction("ома 120", TODAY)

        self.assertEqual(parsed.amount, Decimal("120"))
        self.assertEqual(parsed.type, TransactionType.expense)
        self.assertEqual(parsed.category, "home")
        self.assertEqual(parsed.merchant, "oma")

    def test_yesterday_date(self) -> None:
        parsed = parse_transaction("вчера 42 biedronka", TODAY)

        self.assertEqual(parsed.occurred_on, date(2026, 5, 10))
        self.assertEqual(parsed.merchant, "biedronka")

    def test_dot_date(self) -> None:
        parsed = parse_transaction("12.05 такси 18", TODAY)

        self.assertEqual(parsed.amount, Decimal("18"))
        self.assertEqual(parsed.occurred_on, date(2026, 5, 12))
        self.assertEqual(parsed.category, "transport")

    def test_car_expense(self) -> None:
        parsed = parse_transaction("заправка 250", TODAY)

        self.assertEqual(parsed.amount, Decimal("250"))
        self.assertEqual(parsed.type, TransactionType.expense)
        self.assertEqual(parsed.category, "car")

    def test_car_repair_is_car_not_home(self) -> None:
        parsed = parse_transaction("ремонт машины 2000", TODAY)

        self.assertEqual(parsed.amount, Decimal("2000"))
        self.assertEqual(parsed.type, TransactionType.expense)
        self.assertEqual(parsed.category, "car")

    def test_home_repair_is_home(self) -> None:
        parsed = parse_transaction("ремонт квартиры 500", TODAY)

        self.assertEqual(parsed.amount, Decimal("500"))
        self.assertEqual(parsed.type, TransactionType.expense)
        self.assertEqual(parsed.category, "home")

    def test_dentist_is_health(self) -> None:
        parsed = parse_transaction("стоматолог 180", TODAY)

        self.assertEqual(parsed.amount, Decimal("180"))
        self.assertEqual(parsed.type, TransactionType.expense)
        self.assertEqual(parsed.category, "health")

    def test_medicine_is_health(self) -> None:
        parsed = parse_transaction("лекарства 35", TODAY)

        self.assertEqual(parsed.amount, Decimal("35"))
        self.assertEqual(parsed.type, TransactionType.expense)
        self.assertEqual(parsed.category, "health")

    def test_gym_is_sport(self) -> None:
        parsed = parse_transaction("спортзал 90", TODAY)

        self.assertEqual(parsed.amount, Decimal("90"))
        self.assertEqual(parsed.type, TransactionType.expense)
        self.assertEqual(parsed.category, "sport")

    def test_pool_is_sport(self) -> None:
        parsed = parse_transaction("бассейн 40", TODAY)

        self.assertEqual(parsed.amount, Decimal("40"))
        self.assertEqual(parsed.type, TransactionType.expense)
        self.assertEqual(parsed.category, "sport")

    def test_hotel_is_travel(self) -> None:
        parsed = parse_transaction("отель 300", TODAY)

        self.assertEqual(parsed.amount, Decimal("300"))
        self.assertEqual(parsed.type, TransactionType.expense)
        self.assertEqual(parsed.category, "travel")

    def test_booking_is_travel_merchant(self) -> None:
        parsed = parse_transaction("booking 120", TODAY)

        self.assertEqual(parsed.amount, Decimal("120"))
        self.assertEqual(parsed.type, TransactionType.expense)
        self.assertEqual(parsed.category, "travel")
        self.assertEqual(parsed.merchant, "booking")

    def test_museum_is_culture(self) -> None:
        parsed = parse_transaction("музей 25", TODAY)

        self.assertEqual(parsed.amount, Decimal("25"))
        self.assertEqual(parsed.type, TransactionType.expense)
        self.assertEqual(parsed.category, "culture")

    def test_theatre_is_culture(self) -> None:
        parsed = parse_transaction("театр 80", TODAY)

        self.assertEqual(parsed.amount, Decimal("80"))
        self.assertEqual(parsed.type, TransactionType.expense)
        self.assertEqual(parsed.category, "culture")

    def test_month_date(self) -> None:
        parsed = parse_transaction("5 мая кафе 25", TODAY)

        self.assertEqual(parsed.amount, Decimal("25"))
        self.assertEqual(parsed.occurred_on, date(2026, 5, 5))
        self.assertEqual(parsed.category, "cafes")

    def test_month_date_before_amount_and_merchant(self) -> None:
        parsed = parse_transaction("5 мая 50 евроопт", TODAY)

        self.assertEqual(parsed.amount, Decimal("50"))
        self.assertEqual(parsed.occurred_on, date(2026, 5, 5))
        self.assertEqual(parsed.category, "groceries")
        self.assertEqual(parsed.merchant, "euroopt")

    def test_command_word_month_date_before_amount_and_merchant(self) -> None:
        parsed = parse_transaction("внеси 6 мая 50 евроопт", TODAY)

        self.assertEqual(parsed.amount, Decimal("50"))
        self.assertEqual(parsed.occurred_on, date(2026, 5, 6))
        self.assertEqual(parsed.category, "groceries")
        self.assertEqual(parsed.merchant, "euroopt")
