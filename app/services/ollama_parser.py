import json
from datetime import date
from decimal import Decimal, InvalidOperation
from typing import Any

import httpx

from app.core.config import Settings
from app.core.currencies import normalize_currency
from app.core.types import TransactionType
from app.services.parser import ParsedTransaction


TRANSACTION_SCHEMA = {
    "type": "object",
    "properties": {
        "amount": {"type": "number"},
        "type": {"type": "string", "enum": ["income", "expense"]},
        "category": {
            "type": "string",
                "enum": [
                    "income",
                    "groceries",
                    "cafes",
                    "car",
                    "transport",
                    "rent",
                    "utilities",
                    "health",
                    "delivery",
                    "personal_care",
                    "home",
                    "shopping",
                    "sport",
                    "education",
                    "travel",
                    "culture",
                    "subscriptions",
                    "entertainment",
                    "other",
                ],
        },
        "merchant": {"type": ["string", "null"]},
        "occurred_on": {"type": "string", "format": "date"},
        "note": {"type": ["string", "null"]},
        "currency": {"type": "string"},
    },
    "required": ["amount", "type", "category", "merchant", "occurred_on", "note", "currency"],
    "additionalProperties": False,
}


async def parse_with_ollama(
    text: str,
    today: date,
    settings: Settings,
    default_currency: str = "PLN",
) -> ParsedTransaction:
    prompt = _build_prompt(text, today, default_currency)
    payload = {
        "model": settings.ollama_model,
        "stream": False,
        "format": TRANSACTION_SCHEMA,
        "options": {"temperature": 0},
        "messages": [
            {
                "role": "system",
                "content": (
                    "Ты извлекаешь финансовую транзакцию из короткого сообщения. "
                    f"Верни только JSON по схеме. Валюта по умолчанию {default_currency}. "
                    "Если дата не указана, используй today. "
                    "merchant должен быть короткой меткой магазина или null. "
                    "Если в сообщении есть название магазина, это расход, а не доход."
                ),
            },
            {"role": "user", "content": prompt},
        ],
    }

    async with httpx.AsyncClient(timeout=settings.ollama_timeout_seconds) as client:
        response = await client.post(f"{settings.ollama_url.rstrip('/')}/api/chat", json=payload)
        response.raise_for_status()

    content = response.json()["message"]["content"]
    data = json.loads(content)
    return _validate_ollama_payload(data, default_currency)


def _build_prompt(text: str, today: date, default_currency: str) -> str:
    return (
        f"today: {today.isoformat()}\n"
        f"default_currency: {default_currency}\n"
        f"message: {text}\n\n"
        "Категории:\n"
        "- income: зарплата, возврат, перевод, любой доход\n"
        "- groceries: продукты, супермаркеты, Lidl, Biedronka, Zabka, Auchan, Carrefour, Netto, Aldi, Kaufland, Dino, Spar, Topaz, Euroopt/Евроопт, Грошик, Соседи, Корона, Гиппо, Виталюр, Санта, Простор, Mart Inn, Копеечка\n"
        "- cafes: кафе, кофе, рестораны, бары\n"
        "- delivery: доставка еды, еда на дом, заказ еды, Wolt, Glovo, Pyszne, Uber Eats, Bolt Food, Яндекс Еда\n"
        "- car: авто, машина, бензин, топливо, заправка, ремонт машины, автосервис, страховка, парковка\n"
        "- transport: такси, общественный транспорт, поездки\n"
        "- rent: аренда жилья, оплата квартиры, квартплата\n"
        "- utilities: коммунальные услуги, коммуналка, интернет, связь, мобильная связь, телефон, свет, газ, вода\n"
        "- health: медицина, врачи, стоматологи, клиники, больницы, анализы, аптеки, лекарства, Dr.Max, Ziko, Белфармация, Планета здоровья\n"
        "- personal_care: уход за собой, косметика, бытовая химия, Rossmann/Росман, Hebe, Natura, Sephora, Douglas, Notino, Остров чистоты, Мила\n"
        "- home: дом, ремонт квартиры/дома, стройматериалы, мебель, хозтовары, Castorama, Leroy Merlin, OBI, IKEA, JYSK, PSB Mrówka, ОМА, Материк\n"
        "- shopping: одежда, техника, товары, интернет-магазины, маркетплейсы, Allegro, AliExpress, Amazon, Temu, Shein, Wildberries, Ozon, Kufar, 21vek/21 век, OZ.by, Onliner, Media Expert, RTV Euro AGD, X-Kom, Zara, Reserved, Sinsay, CCC\n"
        "- sport: спортзал, фитнес, тренер, бассейн, йога, спорттовары, абонемент, Decathlon, Intersport, Спортмастер\n"
        "- education: образование, обучение, курсы, уроки, репетитор, школа, университет, тренинг, мастер-класс\n"
        "- travel: путешествия, туризм, поездка, отпуск, отели, авиабилеты, визы, багаж, экскурсии\n"
        "- culture: культурные места, музеи, театр, выставки, галереи, концерты, опера, балет\n"
        "- subscriptions: регулярные подписки и сервисы, Netflix, Spotify, YouTube Premium, iCloud, Google One, ChatGPT, Telegram Premium, Apple Music, Яндекс Плюс, Кинопоиск, Steam, PS Plus, Xbox Game Pass\n"
        "- entertainment: развлечения, аквапарк, парк аттракционов, боулинг, квесты, кино, игры, события\n"
        "- other: если ничего не подходит"
    )


def _validate_ollama_payload(data: dict[str, Any], default_currency: str) -> ParsedTransaction:
    try:
        amount = Decimal(str(data["amount"]))
        tx_type = TransactionType(data["type"])
        occurred_on = date.fromisoformat(data["occurred_on"])
    except (KeyError, InvalidOperation, ValueError, TypeError) as exc:
        raise ValueError("Ollama вернула транзакцию в неожиданном формате.") from exc

    category = _clean_optional_text(data.get("category")) or ("income" if tx_type == TransactionType.income else "other")
    merchant = _clean_optional_text(data.get("merchant"))
    note = _clean_optional_text(data.get("note"))
    currency = normalize_currency(_clean_optional_text(data.get("currency"))) or default_currency

    return ParsedTransaction(
        amount=amount,
        type=tx_type,
        category=category,
        merchant=merchant,
        occurred_on=occurred_on,
        note=note,
        currency=currency,
    )


def _clean_optional_text(value: Any) -> str | None:
    if value is None:
        return None
    cleaned = str(value).strip().lower()
    if not cleaned or cleaned in {"null", "none", "-"}:
        return None
    return cleaned
