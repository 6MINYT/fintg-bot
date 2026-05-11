import re
from dataclasses import dataclass
from datetime import date, timedelta
from decimal import Decimal, InvalidOperation

from app.core.currencies import normalize_currency
from app.core.types import TransactionType


MERCHANT_ALIASES = {
    # Groceries: Poland
    "lidl": ("lidl", "лидл"),
    "biedronka": ("biedronka", "бедронка", "бидронка", "бєдронка"),
    "zabka": ("zabka", "żabka", "жабка", "забка"),
    "auchan": ("auchan", "ашан"),
    "carrefour": ("carrefour", "карфур", "каррефур", "коррефур", "карефур", "корефур", "карrefour"),
    "netto": ("netto", "нетто"),
    "aldi": ("aldi", "альди", "алди"),
    "kaufland": ("kaufland", "кауфланд"),
    "dino": ("dino", "дино"),
    "stokrotka": ("stokrotka", "стокротка"),
    "lewiatan": ("lewiatan", "левиатан"),
    "polomarket": ("polomarket", "поло маркет"),
    "delikatesy centrum": ("delikatesy centrum", "деликатесы центр"),
    "intermarche": ("intermarche", "intermarché", "интермарше"),
    "selgros": ("selgros", "сельгрос"),
    "makro": ("makro", "макро"),
    "spar": ("spar", "спар"),
    "topaz": ("topaz", "топаз"),
    "frac": ("frac", "фрац"),
    "spolem": ("spolem", "społem", "сполем"),
    # Groceries: Belarus
    "euroopt": ("евроопт", "еврорт", "европт", "evroopt", "euroopt"),
    "groshyk": ("грошик", "groshyk"),
    "sosedi": ("соседи", "sosedi"),
    "korona": ("корона", "korona"),
    "hippo": ("гиппо", "hippo"),
    "vitalur": ("виталюр", "vitalur"),
    "santa": ("санта", "santa"),
    "green": ("green", "грин"),
    "belmarket": ("белмаркет", "belmarket"),
    "rublevskiy": ("рублевский", "рублёвский", "rublevskiy"),
    "almi": ("алми", "almi"),
    "vesta": ("веста", "vesta"),
    "prostore": ("простор", "prostore"),
    "mart inn": ("мартин", "mart inn", "martinn"),
    "kopeechka": ("копеечка", "kopeechka"),
    "rodnaya storona": ("родная сторона", "rodnaya storona"),
    # Marketplaces / online stores
    "allegro": ("allegro", "аллегро", "алегро"),
    "aliexpress": ("aliexpress", "ali express", "алиэкспресс", "али экспресс"),
    "amazon": ("amazon", "амазон"),
    "temu": ("temu", "тему"),
    "shein": ("shein", "шеин", "шейн"),
    "wildberries": ("wildberries", "wildberries.by", "вайлдберриз", "вб"),
    "ozon": ("ozon", "озон"),
    "kufar": ("kufar", "куфар"),
    "21vek": ("21vek", "21 vek", "21 век", "двадцать первый век"),
    "oz.by": ("oz.by", "оз бай", "oz by"),
    "onliner": ("onliner", "онлайнер"),
    "empik": ("empik", "эмпик"),
    # Electronics / appliances
    "media expert": ("media expert", "mediaexpert", "медиа эксперт"),
    "rtv euro agd": ("rtv euro agd", "euro agd", "евро агд"),
    "media markt": ("media markt", "mediamarkt", "медиа маркт"),
    "x-kom": ("x-kom", "xkom", "икском"),
    "komputronik": ("komputronik", "компутроник"),
    "neonet": ("neonet", "неонет"),
    "morele": ("morele", "morele.net", "мореле"),
    "5 element": ("5 element", "5 элемент", "пятый элемент"),
    "electrosila": ("электросила", "electrosila"),
    "sila": ("сила", "sila.by"),
    # Clothing / shoes
    "zara": ("zara", "зара"),
    "h&m": ("h&m", "hm", "ашэм", "эйч энд эм"),
    "reserved": ("reserved", "резервед"),
    "sinsay": ("sinsay", "синсей"),
    "cropp": ("cropp", "кропп"),
    "house": ("house", "хаус"),
    "mohito": ("mohito", "мохито"),
    "ccc": ("ccc", "ццц"),
    "deichmann": ("deichmann", "дайхман", "дейхман"),
    "eobuwie": ("eobuwie", "эобуве"),
    # Personal care / drugstores
    "rossmann": ("rossmann", "rossman", "россман", "росман"),
    "hebe": ("hebe", "хебе"),
    "natura": ("natura", "натура"),
    "dm": ("dm", "дм"),
    "super-pharm": ("super-pharm", "super pharm", "суперфарм", "супер фарм"),
    "ostrov chistoty": ("остров чистоты", "остров", "ostrov chistoty"),
    "mila": ("мила", "mila"),
    "kosmo": ("космо", "kosmo"),
    "sephora": ("sephora", "сефора"),
    "douglas": ("douglas", "дуглас"),
    "notino": ("notino", "нотино"),
    "yves rocher": ("yves rocher", "ив роше"),
    "gold apple": ("gold apple", "золотое яблоко"),
    "makeup": ("makeup", "make up", "мейкап"),
    # Pharmacies
    "apteka gemini": ("gemini", "аптека gemini", "гемини"),
    "apteka doz": ("doz", "аптека doz", "доз"),
    "apteka 911": ("аптека 911", "911"),
    "apteka ru": ("аптека ру", "apteka ru"),
    "dr.max": ("dr.max", "dr max", "доктор макс"),
    "ziko": ("ziko", "зико"),
    "apteka melissa": ("melissa", "аптека melissa", "мелисса"),
    "apteka od serca": ("apteka od serca", "od serca", "од серца"),
    "belpharmacy": ("белфармация", "belpharmacy"),
    "planeta zdorovya": ("планета здоровья", "planeta zdorovya"),
    # Taxi / transport
    "bolt": ("bolt", "болт"),
    "uber": ("uber", "убер"),
    "freenow": ("free now", "freenow", "фри нау"),
    "itaxi": ("itaxi", "i taxi", "ай такси"),
    "yandex taxi": ("яндекс такси", "yandex taxi", "yandex go", "яндекс go"),
    # Food delivery
    "wolt": ("wolt", "волт", "вольт"),
    "glovo": ("glovo", "глово"),
    "pyszne": ("pyszne", "pyszne.pl", "пышне", "пишне"),
    "uber eats": ("uber eats", "ubereats", "убер eats", "убер итс"),
    "bolt food": ("bolt food", "boltfood", "болт фуд"),
    "yandex food": ("яндекс еда", "yandex food"),
    "eda.by": ("eda.by", "еда бай", "edaby"),
    # Fuel / car
    "orlen": ("orlen", "орлен"),
    "bp": ("bp", "би пи"),
    "shell": ("shell", "шелл"),
    "circle k": ("circle k", "circlek", "циркл к"),
    "lotos": ("lotos", "лотос"),
    "amic": ("amic", "амик"),
    "belorusneft": ("белоруснефть", "беларуснефть", "belorusneft"),
    "a-100": ("а-100", "а100", "a-100", "a100"),
    "lukoil": ("лукойл", "lukoil"),
    # Home / household
    "castorama": ("castorama", "касторама"),
    "leroy merlin": ("leroy merlin", "леруа", "леруа мерлен"),
    "obi": ("obi", "оби"),
    "ikea": ("ikea", "икеа"),
    "jysk": ("jysk", "юск", "йиск"),
    "brw": ("brw", "black red white", "блэк ред вайт"),
    "oma": ("ома", "oma"),
    "materik": ("материк", "materik"),
    "bricomarche": ("bricomarche", "bricomarché", "брикомарше"),
    "psb mrowka": ("psb mrowka", "psb mrówka", "mrowka", "mrówka", "мрувка"),
    "komfort": ("komfort", "комфорт"),
    "akson": ("akson", "аксон"),
    # Sport
    "decathlon": ("decathlon", "декатлон"),
    "intersport": ("intersport", "интерспорт"),
    "sportmaster": ("спортмастер", "sportmaster"),
    # Travel
    "booking": ("booking", "букинг"),
    "airbnb": ("airbnb", "эйрбнб", "аирбнб"),
    "ryanair": ("ryanair", "райнэйр", "раянэйр"),
    "wizzair": ("wizzair", "wizz air", "виззэйр", "виз эйр"),
    # Cafes / restaurants
    "mcdonalds": (
        "mcdonalds",
        "mcdonald's",
        "mcdonald",
        "макдоналдс",
        "макдоналтдс",
        "макдональдс",
        "макдональд",
        "мак",
        "макдак",
    ),
    "kfc": ("kfc", "кфс", "кфц"),
    "burger king": ("burger king", "бургер кинг"),
    # Subscriptions
    "netflix": ("netflix", "нетфликс"),
    "spotify": ("spotify", "спотифай"),
    "youtube premium": ("youtube premium", "ютуб премиум", "youtube"),
    "icloud": ("icloud", "айклауд", "i cloud"),
    "google one": ("google one", "гугл one", "гугл ван"),
    "chatgpt": ("chatgpt", "chat gpt", "чатгпт", "чат gpt"),
    "telegram premium": ("telegram premium", "телеграм премиум"),
    "apple music": ("apple music", "эпл music", "эпл мьюзик"),
    "yandex plus": ("yandex plus", "яндекс плюс", "плюс"),
    "kinopoisk": ("kinopoisk", "кинопоиск"),
    "ivi": ("ivi", "иви"),
    "steam": ("steam", "стим"),
    "ps plus": ("ps plus", "playstation plus", "ps+", "пс плюс"),
    "xbox game pass": ("xbox game pass", "game pass", "гейм пасс"),
}

MERCHANT_CATEGORIES = {
    "rossmann": "personal_care",
    "hebe": "personal_care",
    "natura": "personal_care",
    "dm": "personal_care",
    "super-pharm": "personal_care",
    "ostrov chistoty": "personal_care",
    "mila": "personal_care",
    "kosmo": "personal_care",
    "apteka gemini": "health",
    "apteka doz": "health",
    "apteka 911": "health",
    "apteka ru": "health",
    "bolt": "transport",
    "uber": "transport",
    "freenow": "transport",
    "itaxi": "transport",
    "yandex taxi": "transport",
    "wolt": "delivery",
    "glovo": "delivery",
    "pyszne": "delivery",
    "uber eats": "delivery",
    "bolt food": "delivery",
    "yandex food": "delivery",
    "eda.by": "delivery",
    "allegro": "shopping",
    "aliexpress": "shopping",
    "amazon": "shopping",
    "temu": "shopping",
    "shein": "shopping",
    "wildberries": "shopping",
    "ozon": "shopping",
    "kufar": "shopping",
    "21vek": "shopping",
    "oz.by": "shopping",
    "onliner": "shopping",
    "empik": "shopping",
    "media expert": "shopping",
    "rtv euro agd": "shopping",
    "media markt": "shopping",
    "x-kom": "shopping",
    "komputronik": "shopping",
    "neonet": "shopping",
    "morele": "shopping",
    "5 element": "shopping",
    "electrosila": "shopping",
    "sila": "shopping",
    "zara": "shopping",
    "h&m": "shopping",
    "reserved": "shopping",
    "sinsay": "shopping",
    "cropp": "shopping",
    "house": "shopping",
    "mohito": "shopping",
    "ccc": "shopping",
    "deichmann": "shopping",
    "eobuwie": "shopping",
    "sephora": "personal_care",
    "douglas": "personal_care",
    "notino": "personal_care",
    "yves rocher": "personal_care",
    "gold apple": "personal_care",
    "makeup": "personal_care",
    "dr.max": "health",
    "ziko": "health",
    "apteka melissa": "health",
    "apteka od serca": "health",
    "belpharmacy": "health",
    "planeta zdorovya": "health",
    "orlen": "car",
    "bp": "car",
    "shell": "car",
    "circle k": "car",
    "lotos": "car",
    "amic": "car",
    "belorusneft": "car",
    "a-100": "car",
    "lukoil": "car",
    "castorama": "home",
    "leroy merlin": "home",
    "obi": "home",
    "ikea": "home",
    "jysk": "home",
    "brw": "home",
    "oma": "home",
    "materik": "home",
    "bricomarche": "home",
    "psb mrowka": "home",
    "komfort": "home",
    "akson": "home",
    "decathlon": "sport",
    "intersport": "sport",
    "sportmaster": "sport",
    "booking": "travel",
    "airbnb": "travel",
    "ryanair": "travel",
    "wizzair": "travel",
    "mcdonalds": "cafes",
    "kfc": "cafes",
    "burger king": "cafes",
    "netflix": "subscriptions",
    "spotify": "subscriptions",
    "youtube premium": "subscriptions",
    "icloud": "subscriptions",
    "google one": "subscriptions",
    "chatgpt": "subscriptions",
    "telegram premium": "subscriptions",
    "apple music": "subscriptions",
    "yandex plus": "subscriptions",
    "kinopoisk": "subscriptions",
    "ivi": "subscriptions",
    "steam": "subscriptions",
    "ps plus": "subscriptions",
    "xbox game pass": "subscriptions",
}

CATEGORY_RULES = {
    "income": {
        "type": TransactionType.income,
        "keywords": ("получил", "получила", "доход", "зарплата", "зп", "salary", "income", "перевод"),
    },
    "groceries": {
        "type": TransactionType.expense,
        "keywords": (
            "lidl",
            "лидл",
            "biedronka",
            "бедронка",
            "бидронка",
            "zabka",
            "żabka",
            "жабка",
            "продукты",
            "еда домой",
            "магазин",
            "grocery",
        ),
    },
    "cafes": {
        "type": TransactionType.expense,
        "keywords": (
            "кафе",
            "кофе",
            "ресторан",
            "бар",
            "mcdonald",
            "макдоналдс",
            "макдоналтдс",
            "макдональдс",
            "макдональд",
            "макдак",
            "kfc",
            "кфс",
            "pizza",
        ),
    },
    "delivery": {
        "type": TransactionType.expense,
        "keywords": (
            "доставка",
            "доставка еды",
            "еда на дом",
            "заказ еды",
            "привезли еду",
            "курьер еда",
            "роллы доставка",
            "суши доставка",
            "пицца доставка",
            "wolt",
            "glovo",
            "pyszne",
            "uber eats",
            "ubereats",
            "bolt food",
            "boltfood",
            "яндекс еда",
            "еда бай",
            "eda.by",
            "delivery food",
            "food delivery",
        ),
    },
    "car": {
        "type": TransactionType.expense,
        "keywords": (
            "авто",
            "машина",
            "бензин",
            "топливо",
            "заправка",
            "страховка авто",
            "ремонт авто",
            "ремонт машины",
            "ремонт машина",
            "ремонт автомобиля",
            "сервис авто",
            "автосервис",
            "шиномонтаж",
            "парковка",
            "parking",
            "fuel",
            "car",
        ),
    },
    "transport": {
        "type": TransactionType.expense,
        "keywords": ("такси", "uber", "bolt", "транспорт", "трансорт", "автобус", "метро", "трамвай", "поезд", "train"),
    },
    "home": {
        "type": TransactionType.expense,
        "keywords": (
            "дом",
            "ремонт дома",
            "ремонт квартиры",
            "стройматериалы",
            "строительные материалы",
            "материалы для ремонта",
            "мебель",
            "хозтовары",
            "household",
            "home",
        ),
    },
    "rent": {
        "type": TransactionType.expense,
        "keywords": ("аренда", "квартира", "квартиры", "жилье", "жильё", "оплата квартиры", "квартплата", "rent"),
    },
    "utilities": {
        "type": TransactionType.expense,
        "keywords": (
            "коммунал",
            "коммуналка",
            "свет",
            "газ",
            "вода",
            "интернет",
            "связь",
            "мобильная связь",
            "телефон",
            "мобильный",
            "utilities",
        ),
    },
    "health": {
        "type": TransactionType.expense,
        "keywords": (
            "аптека",
            "врач",
            "врачи",
            "доктор",
            "доктора",
            "медицина",
            "медицин",
            "клиника",
            "поликлиника",
            "больница",
            "стоматолог",
            "стоматологу",
            "стоматология",
            "зубной",
            "дантист",
            "лекар",
            "таблетки",
            "анализы",
            "анализ",
            "здоров",
            "pharmacy",
            "doctor",
            "dentist",
            "medicine",
        ),
    },
    "personal_care": {
        "type": TransactionType.expense,
        "keywords": (
            "уход",
            "косметика",
            "шампунь",
            "гель",
            "бритва",
            "зубная паста",
            "дрогери",
            "drogeria",
        ),
    },
    "shopping": {
        "type": TransactionType.expense,
        "keywords": (
            "одежда",
            "техника",
            "товары",
            "маркетплейс",
            "интернет магазин",
            "интернет-магазин",
            "онлайн магазин",
            "онлайн-магазин",
            "allegro",
            "аллегро",
            "алегро",
            "aliexpress",
            "алиэкспресс",
            "amazon",
            "temu",
            "wildberries",
            "вайлдберриз",
            "ozon",
            "озон",
            "kufar",
            "куфар",
            "21 век",
            "21vek",
            "oz.by",
            "media expert",
            "media markt",
            "x-kom",
            "zara",
            "reserved",
            "sinsay",
            "ccc",
            "shopping",
        ),
    },
    "sport": {
        "type": TransactionType.expense,
        "keywords": (
            "спорт",
            "спортзал",
            "зал",
            "фитнес",
            "тренер",
            "тренировка",
            "бассейн",
            "йога",
            "пилатес",
            "абонемент",
            "спорттовары",
            "спортивная форма",
            "gym",
            "fitness",
            "sport",
        ),
    },
    "education": {
        "type": TransactionType.expense,
        "keywords": (
            "образование",
            "обучение",
            "учеба",
            "учёба",
            "курсы",
            "курс",
            "урок",
            "уроки",
            "занятия",
            "репетитор",
            "репетитору",
            "школа",
            "университет",
            "универ",
            "институт",
            "лекция",
            "семинар",
            "тренинг",
            "мастер-класс",
            "мастеркласс",
            "английский",
            "польский язык",
            "education",
            "course",
            "courses",
            "lesson",
            "school",
            "university",
        ),
    },
    "travel": {
        "type": TransactionType.expense,
        "keywords": (
            "путешествие",
            "путешествия",
            "туризм",
            "поездка",
            "отпуск",
            "отель",
            "гостиница",
            "хостел",
            "апартаменты",
            "жилье в поездке",
            "жильё в поездке",
            "авиабилеты",
            "билеты на самолет",
            "билет на самолет",
            "самолет",
            "самолёт",
            "перелет",
            "перелёт",
            "багаж",
            "виза",
            "страховка путешествия",
            "экскурсия",
            "тур",
            "travel",
            "trip",
            "hotel",
            "flight",
            "visa",
        ),
    },
    "culture": {
        "type": TransactionType.expense,
        "keywords": (
            "культура",
            "музей",
            "музеи",
            "театр",
            "опера",
            "балет",
            "выставка",
            "галерея",
            "концерт",
            "филармония",
            "билет в музей",
            "билет в театр",
            "экспозиция",
            "culture",
            "museum",
            "theatre",
            "theater",
            "gallery",
            "concert",
        ),
    },
    "subscriptions": {
        "type": TransactionType.expense,
        "keywords": (
            "подписка",
            "подписки",
            "абонплата",
            "ежемесячный платеж",
            "netflix",
            "нетфликс",
            "spotify",
            "спотифай",
            "youtube premium",
            "ютуб премиум",
            "icloud",
            "айклауд",
            "google one",
            "chatgpt",
            "чатгпт",
            "telegram premium",
            "телеграм премиум",
            "apple music",
            "yandex plus",
            "яндекс плюс",
            "кинопоиск",
            "ivi",
            "steam",
            "ps plus",
            "game pass",
            "subscription",
            "subscriptions",
        ),
    },
    "entertainment": {
        "type": TransactionType.expense,
        "keywords": (
            "развлечение",
            "развлечения",
            "аквапарк",
            "парк аттракционов",
            "аттракционы",
            "батуты",
            "боулинг",
            "квест",
            "игры",
            "кино",
            "entertainment",
        ),
    },
}

MONTHS = {
    "января": 1,
    "февраля": 2,
    "марта": 3,
    "апреля": 4,
    "мая": 5,
    "июня": 6,
    "июля": 7,
    "августа": 8,
    "сентября": 9,
    "октября": 10,
    "ноября": 11,
    "декабря": 12,
    "stycznia": 1,
    "lutego": 2,
    "marca": 3,
    "kwietnia": 4,
    "maja": 5,
    "czerwca": 6,
    "lipca": 7,
    "sierpnia": 8,
    "września": 9,
    "wrzesnia": 9,
    "października": 10,
    "pazdziernika": 10,
    "listopada": 11,
    "grudnia": 12,
}

CURRENCY_RE_PART = (
    r"(?:zł|zl|pln|зл|злот(?:ый|ых|ые|ого)?|\$|usd|доллар(?:а|ов)?|бакс(?:а|ов)?|"
    r"byn|br|бел\.?\s*руб|белруб|рб\s*руб(?:ль|лей)?|руб(?:ль|ля|лей)?|eur|€|евро)(?!\w)"
)
AMOUNT_RE = re.compile(rf"(?<!\w)(\d+(?:[.,]\d{{1,2}})?)\s*({CURRENCY_RE_PART})?", re.I)
ISO_DATE_RE = re.compile(r"\b(20\d{2})-(\d{1,2})-(\d{1,2})\b")
DOT_DATE_RE = re.compile(r"\b(\d{1,2})[./](\d{1,2})(?:[./](20\d{2}))?\b")
MONTH_DATE_RE = re.compile(r"\b(\d{1,2})\s+([а-яёąćęłńóśźż]+)(?:\s+(20\d{2}))?\b", re.I)


@dataclass(frozen=True)
class ParsedTransaction:
    amount: Decimal
    type: TransactionType
    category: str
    merchant: str | None
    occurred_on: date
    note: str | None
    currency: str = "PLN"


def parse_transaction(text: str, today: date, default_currency: str = "PLN") -> ParsedTransaction:
    normalized = text.strip().lower()
    occurred_on = _extract_date(normalized, today)
    tx_type, category, merchant = classify_transaction_text(normalized)
    amount_text = _remove_merchant_text(_remove_date_text(normalized), merchant)
    amount = _extract_amount(amount_text)
    note = _cleanup_note(text)
    currency = _extract_currency(amount_text, default_currency)

    return ParsedTransaction(
        amount=amount,
        type=tx_type,
        category=category,
        merchant=merchant,
        occurred_on=occurred_on,
        note=note,
        currency=currency,
    )


def classify_transaction_text(text: str) -> tuple[TransactionType, str, str | None]:
    normalized = text.strip().lower()
    merchant = _extract_merchant(normalized)
    tx_type, category = _classify(normalized, merchant)
    return tx_type, category, merchant


def _extract_amount(text: str) -> Decimal:
    match = AMOUNT_RE.search(text)
    if not match:
        raise ValueError("Не нашел сумму. Напиши, например: 300 lidl или получил 500 злотых")

    try:
        return Decimal(match.group(1).replace(",", "."))
    except InvalidOperation as exc:
        raise ValueError("Не смог прочитать сумму.") from exc


def _extract_currency(text: str, default_currency: str) -> str:
    match = AMOUNT_RE.search(text)
    if not match:
        return default_currency

    return normalize_currency(match.group(2)) or default_currency


def _extract_date(text: str, today: date) -> date:
    if "позавчера" in text:
        return today - timedelta(days=2)
    if "вчера" in text or "yesterday" in text:
        return today - timedelta(days=1)
    if "сегодня" in text or "today" in text:
        return today

    iso_match = ISO_DATE_RE.search(text)
    if iso_match:
        year, month, day = map(int, iso_match.groups())
        return date(year, month, day)

    month_match = MONTH_DATE_RE.search(text)
    if month_match:
        day, month_name, year = month_match.groups()
        month = MONTHS.get(month_name.lower())
        if month:
            return date(int(year or today.year), month, int(day))

    dot_match = DOT_DATE_RE.search(text)
    if dot_match and _is_dot_date_match(text, dot_match):
        day, month, year = dot_match.groups()
        return date(int(year or today.year), int(month), int(day))

    return today


def _extract_merchant(text: str) -> str | None:
    for merchant, aliases in MERCHANT_ALIASES.items():
        if any(_contains_alias(text, alias) for alias in aliases):
            return merchant
    return None


def _contains_alias(text: str, alias: str) -> bool:
    return re.search(rf"(?<!\w){re.escape(alias.lower())}(?!\w)", text) is not None


def _remove_merchant_text(text: str, merchant: str | None) -> str:
    if not merchant:
        return text

    cleaned = text
    aliases = sorted(MERCHANT_ALIASES.get(merchant, ()), key=len, reverse=True)
    for alias in aliases:
        cleaned = re.sub(rf"(?<!\w){re.escape(alias.lower())}(?!\w)", " ", cleaned, flags=re.I)
    return cleaned


def _classify(text: str, merchant: str | None) -> tuple[TransactionType, str]:
    if merchant:
        return TransactionType.expense, MERCHANT_CATEGORIES.get(merchant, "groceries")

    for category, rule in CATEGORY_RULES.items():
        if any(keyword in text for keyword in rule["keywords"]):
            return rule["type"], category

    return TransactionType.expense, "other"


def _cleanup_note(text: str) -> str | None:
    cleaned = _remove_date_text(text)
    cleaned = AMOUNT_RE.sub("", cleaned, count=1)
    cleaned = " ".join(cleaned.split())
    return cleaned or None


def _remove_date_text(text: str) -> str:
    cleaned = text
    cleaned = ISO_DATE_RE.sub("", cleaned)
    cleaned = MONTH_DATE_RE.sub(_remove_month_date_match, cleaned)
    cleaned = DOT_DATE_RE.sub(lambda match: "" if _is_dot_date_match(cleaned, match) else match.group(0), cleaned)
    for word in ("сегодня", "вчера", "позавчера", "today", "yesterday"):
        cleaned = re.sub(rf"\b{word}\b", "", cleaned, flags=re.I)
    return cleaned


def _is_dot_date_match(text: str, match: re.Match) -> bool:
    if match.group(3):
        return True

    separator = text[match.start(1) + len(match.group(1))]
    if separator == "/":
        return True

    without_match = f"{text[: match.start()]} {text[match.end() :]}"
    return AMOUNT_RE.search(without_match) is not None


def _remove_month_date_match(match: re.Match) -> str:
    month_name = match.group(2).lower()
    return "" if month_name in MONTHS else match.group(0)
