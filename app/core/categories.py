CATEGORY_LABELS = {
    "income": "Доход",
    "groceries": "Продукты",
    "car": "Авто",
    "transport": "Транспорт",
    "rent": "Оплата квартиры",
    "utilities": "Коммуналка и связь",
    "cafes": "Кафе и рестораны",
    "delivery": "Доставка",
    "health": "Здоровье",
    "personal_care": "Уход за собой",
    "home": "Дом и ремонт",
    "shopping": "Покупки",
    "sport": "Спорт",
    "travel": "Путешествия",
    "culture": "Культура",
    "entertainment": "Развлечения",
    "other": "Другое",
}

CATEGORY_ORDER = tuple(category for category in CATEGORY_LABELS if category != "income")

CATEGORY_ALIASES = {
    "income": ("доход", "зарплата", "зп", "income"),
    "groceries": ("продукты", "еда", "магазин", "супермаркет", "groceries"),
    "car": ("авто", "машина", "заправка", "бензин", "car"),
    "transport": ("транспорт", "такси", "метро", "автобус", "transport"),
    "rent": ("квартира", "аренда", "оплата квартиры", "rent"),
    "utilities": ("коммуналка", "связь", "интернет", "utilities"),
    "cafes": ("кафе", "ресторан", "кофе", "cafes"),
    "delivery": (
        "доставка",
        "доставка еды",
        "еда на дом",
        "заказ еды",
        "wolt",
        "glovo",
        "pyszne",
        "uber eats",
        "delivery",
    ),
    "health": (
        "здоровье",
        "медицина",
        "аптека",
        "врач",
        "доктор",
        "стоматолог",
        "стоматология",
        "лекарства",
        "анализы",
        "клиника",
        "health",
    ),
    "personal_care": ("уход", "косметика", "бытовая химия", "personal_care"),
    "home": ("дом", "ремонт дома", "ремонт квартиры", "стройматериалы", "строительные материалы", "мебель", "home"),
    "shopping": (
        "покупки",
        "одежда",
        "техника",
        "маркетплейс",
        "интернет магазин",
        "allegro",
        "aliexpress",
        "wildberries",
        "21 век",
        "shopping",
    ),
    "sport": ("спорт", "зал", "фитнес", "тренер", "бассейн", "йога", "sport"),
    "travel": ("путешествия", "туризм", "поездка", "отпуск", "отель", "билеты", "travel"),
    "culture": ("культура", "музей", "театр", "выставка", "галерея", "концерт", "culture"),
    "entertainment": ("развлечения", "кино", "игры", "entertainment"),
    "other": ("другое", "other"),
}


def category_label(category: str) -> str:
    return CATEGORY_LABELS.get(category, category)


def normalize_category(value: str | None) -> str | None:
    if not value:
        return None

    cleaned = " ".join(value.strip().lower().split())
    for category, aliases in CATEGORY_ALIASES.items():
        if cleaned == category or cleaned in aliases or cleaned == CATEGORY_LABELS[category].lower():
            return category
    return None
