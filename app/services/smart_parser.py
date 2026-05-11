from datetime import date

from app.core.config import Settings
from app.services.ollama_parser import parse_with_ollama
from app.services.parser import ParsedTransaction, parse_transaction


async def parse_transaction_smart(
    text: str,
    today: date,
    settings: Settings,
    default_currency: str = "PLN",
) -> ParsedTransaction:
    if settings.parser_mode == "ollama":
        return await parse_with_ollama(text, today, settings, default_currency)

    try:
        parsed = parse_transaction(text, today, default_currency)
    except ValueError:
        if settings.parser_mode == "rules_then_ollama":
            try:
                return await parse_with_ollama(text, today, settings, default_currency)
            except Exception as exc:
                raise ValueError("Не смог разобрать сообщение правилами, а Ollama сейчас недоступна.") from exc
        raise

    if settings.parser_mode != "rules_then_ollama":
        return parsed

    if _should_ask_ollama(parsed):
        try:
            return await parse_with_ollama(text, today, settings, default_currency)
        except Exception:
            return parsed

    return parsed


def _should_ask_ollama(parsed: ParsedTransaction) -> bool:
    return parsed.category == "other" or (parsed.category == "groceries" and not parsed.merchant)
