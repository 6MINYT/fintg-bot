# FinTG

FinTG is a personal Telegram bot for tracking income and expenses.

It is built around short natural messages such as `300 lidl`, `yesterday 42 biedronka`, or `5 May 60 euroopt`. The bot parses the amount, date, category, merchant, currency, and stores everything in PostgreSQL.

## Features

- Parse simple income and expense messages.
- Detect dates like `today`, `yesterday`, `12.05`, `2026-05-12`, `5 мая`, and Polish month names.
- Categorize popular Polish and Belarusian stores automatically.
- Support groceries, car, transport, rent, utilities, cafes, delivery, health, personal care, home and renovation, shopping, sport, travel, culture, entertainment, and other.
- Keep transaction numbers isolated per Telegram user: each user has their own `#1`, `#2`, `#3`.
- Keep default currency per user: `PLN`, `USD`, `BYN`, or `EUR`.
- Ask for confirmation before suspicious entries, for example category `Other` or amount `0`.
- Let users override categories in text, for example `56 euroopt category groceries` or `56 евроопт категория продукты`.
- Edit and delete records by transaction number.
- Show recent records and records from the last 14 days for quick corrections.
- Generate weekly, monthly, yearly, and custom period reports.
- Export transactions to Excel with transactions, category totals, top merchants, and charts.
- Track monthly category limits.
- Provide admin-only user activity statistics.
- Optional Ollama parser fallback, disabled by default.

## Quick Start

1. Create a Telegram bot with [BotFather](https://t.me/BotFather) and get a token.

2. Create your local environment file:

```bash
cp .env.example .env
```

3. Set at least:

```env
BOT_TOKEN=your-telegram-bot-token
ADMIN_TELEGRAM_IDS=
```

You can get your Telegram ID by sending `/myid` to the bot after it starts. Admin IDs are comma-separated:

```env
ADMIN_TELEGRAM_IDS=123456789,987654321
```

4. Start the app:

```bash
docker compose up -d --build
```

5. Watch logs:

```bash
docker compose logs -f bot
```

## Example Messages

```text
received 500 PLN
300 lidl
yesterday 42 biedronka
12.05 taxi 18
gas 250
euroopt 65
hebe 42
bolt 19
oma 120
2026-05-01 rent 2500
5 мая 60 евроопт
коррефур 60
allegro 120
dr max 45
decathlon 180
```

Russian messages are supported well because the bot was designed around Russian-speaking users in Poland and Belarus:

```text
получил 500 злотых
вчера 42 бедронка
заправка 250
стоматолог 180
доставка еды 44
ремонт машины 2000
измени #12 на 40
удали #12
```

## Main Commands

- `/start` or `/help` - show help and the bottom menu.
- `/menu` - show the bottom menu.
- `/summary` - category totals.
- `/week` - report for the current week.
- `/month` - report for the current month.
- `/month 2026-05` or `/month 05.2026` - report for a selected month.
- `/year` - report for the current year.
- `/categories` - list available categories and aliases.
- `/currency` - show and choose the default currency.
- `/currency BYN` - change default currency.
- `/limit` - show monthly category limits.
- `/limit продукты 800` - set a monthly limit.
- `/limit удали продукты` - delete a category limit.
- `/recent` or `/last` - show recent records with numbers.
- `/edit` - show records from the last 14 days with edit examples.
- `/merchant lidl` - show totals for a merchant.
- `/export` - ask for an export period and send an Excel file.
- `/delete #12` or `/del #12` - delete a record.
- `/myid` - show your Telegram ID.
- `/users` - admin-only user activity statistics.

## Bottom Menu

The bot includes Telegram reply keyboard shortcuts:

- Reports - quick report periods.
- Export - Excel export periods.
- Edit - records from the last 14 days and correction hints.
- Recent - latest records.
- Settings - currency, limits, categories, admin tools.
- Categories - category list.
- Help - main help text.

## Editing Records

Without a number, the bot edits the last record:

```text
измени росман 30
исправь на расход
```

To edit a specific record, use its number:

```text
измени #12 росман 30
измени #12 на 40
измени #12 категория продукты
исправь #12 на расход
```

Numbers are per user, so your `#12` is not your friend's `#12`.

## Deleting Records

```text
удали последнюю запись
удали #12
/delete #12
```

Admin users also get a settings button to clear their own transactions. It does not delete other users, currency settings, or limits.

## Reports

Available report commands:

```text
/week
/month
/year
```

Reports include:

- income, expenses, and balance by currency;
- biggest spending categories;
- top merchants;
- comparison with the previous period;
- simple anomaly detection when a category is at least 2x higher than before.

## Excel Export

Use `/export` and choose a period from the buttons, or write:

```text
/export этот месяц
/export прошлый месяц
/export 3 месяца
/export полгода
/export за год
/export 2026-05
/export 2026-05-01 2026-05-31
```

Natural Russian requests are also supported:

```text
дай мне экспорт за последние полгода
дай мне экспорт за 3 месяца
```

The generated workbook includes:

- transactions;
- totals by category;
- expense chart;
- top merchants.

## Categories

Current categories:

- Income
- Groceries
- Car
- Transport
- Rent
- Utilities and communication
- Cafes and restaurants
- Delivery
- Health
- Personal care
- Home and renovation
- Shopping
- Sport
- Travel
- Culture
- Entertainment
- Other

Category labels shown to users are in Russian.

## Store Recognition

The rules parser recognizes many Polish and Belarusian stores and services, including:

- groceries: Lidl, Biedronka, Zabka, Auchan, Carrefour, Aldi, Kaufland, Euroopt, Green, Vitalur, Korona, Santa, Prostore, Kopeechka;
- personal care: Rossmann, Hebe, Natura, DM, Sephora, Douglas, Notino, Ostrov Chistoty;
- pharmacies: Dr.Max, Ziko, Gemini, DOZ, Belpharmacy, Planeta Zdorovya;
- transport and taxi: Bolt, Uber, Free Now, Yandex Taxi;
- food delivery: Wolt, Glovo, Pyszne, Uber Eats, Bolt Food, Yandex Food;
- fuel and car: Orlen, BP, Shell, Circle K, Lotos, Belorusneft, A-100, Lukoil;
- home and renovation: Castorama, Leroy Merlin, OBI, IKEA, JYSK, OMA, Materik, PSB Mrowka;
- shopping and marketplaces: Allegro, AliExpress, Amazon, Temu, Shein, Wildberries, Ozon, Kufar, 21vek, OZ.by, Onliner, Empik;
- electronics: Media Expert, RTV Euro AGD, Media Markt, X-Kom, Komputronik, 5 Element, Electrosila;
- sport: Decathlon, Intersport, Sportmaster;
- travel: Booking, Airbnb, Ryanair, Wizz Air.

Rules live in `app/services/parser.py` and are intentionally easy to edit.

## Parser Modes

By default the project uses the rules parser:

```env
PARSER_MODE=rules
```

Available modes:

- `rules` - use local rules only.
- `rules_then_ollama` - try rules first, then ask Ollama for uncertain messages.
- `ollama` - always use Ollama.

Ollama services are disabled by default through Docker Compose profiles. To run them:

```bash
docker compose --profile ollama up -d ollama ollama-pull
```

Then set:

```env
PARSER_MODE=rules_then_ollama
OLLAMA_URL=http://ollama:11434
OLLAMA_MODEL=llama3.2:3b
```

## Database Backup And Migration

Create a PostgreSQL dump:

```bash
docker compose exec db pg_dump -U fintg -d fintg > fintg_backup.sql
```

Restore on another machine:

```bash
docker compose up -d db
cat fintg_backup.sql | docker compose exec -T db psql -U fintg -d fintg
docker compose up -d --build bot
```

Do not run two bot instances with the same Telegram token at the same time.

## Local Development

Run parser tests:

```bash
python3 -m unittest app.tests.test_parser
```

Compile-check the app:

```bash
python3 -m compileall -q app
```

## Project Structure

- `app/main.py` - bot entry point.
- `app/bot/handlers.py` - Telegram commands, menus, callbacks, and message handling.
- `app/services/parser.py` - rule-based parsing of amount, date, category, merchant, and currency.
- `app/services/smart_parser.py` - parser mode selection.
- `app/services/ollama_parser.py` - optional Ollama JSON parser.
- `app/services/transactions.py` - database operations and Excel export.
- `app/services/reports.py` - period reports.
- `app/core/categories.py` - category labels and aliases.
- `app/core/currencies.py` - supported currencies and aliases.
- `app/db/models.py` - SQLAlchemy models.
- `app/db/session.py` - database session and lightweight migrations.

## Security Notes

- Do not commit `.env`.
- If a Telegram bot token was ever exposed, rotate it in BotFather.
- Use `ADMIN_TELEGRAM_IDS` for admin-only actions.
- Only one running bot instance should use a given Telegram token.
