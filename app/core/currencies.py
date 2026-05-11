SUPPORTED_CURRENCIES = ("PLN", "USD", "BYN", "EUR")

CURRENCY_LABELS = {
    "PLN": "злотые",
    "USD": "доллары",
    "BYN": "белорусские рубли",
    "EUR": "евро",
}

CURRENCY_ALIASES = {
    "PLN": ("pln", "zł", "zl", "зл", "злотый", "злотых", "злотые", "злотого"),
    "USD": ("usd", "$", "доллар", "доллара", "долларов", "бакс", "бакса", "баксов"),
    "BYN": (
        "byn",
        "br",
        "бел руб",
        "бел. руб",
        "белруб",
        "рб руб",
        "рб рубль",
        "рб рублей",
        "руб",
        "рубль",
        "рубля",
        "рублей",
    ),
    "EUR": ("eur", "€", "евро"),
}


def normalize_currency(value: str | None) -> str | None:
    if not value:
        return None

    cleaned = " ".join(value.strip().lower().replace(".", " ").split())
    for currency, aliases in CURRENCY_ALIASES.items():
        if cleaned == currency.lower() or cleaned in aliases:
            return currency
    return None


def currency_label(currency: str) -> str:
    return CURRENCY_LABELS.get(currency.upper(), currency.upper())
