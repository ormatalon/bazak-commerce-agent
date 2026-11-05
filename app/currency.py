"""Turn a budget in another currency into dollars, with a fixed table of rates.

The model only reads the amount and the currency. This code does the arithmetic, so the
number is the same every time and a test can check it. The rates are a snapshot, not live,
so the reply says "roughly". To refresh them, change the table and the date below.
"""

from app.schemas import SearchSpec

# Units of each currency for one US dollar, from api.frankfurter.dev (European Central Bank rates).
RATES_DATE = "2026-11-04"
UNITS_PER_DOLLAR = {
    "AUD": 1.4255,
    "CAD": 1.3935,
    "CHF": 0.81548,
    "EUR": 0.88755,
    "GBP": 0.74075,
    "ILS": 3.1633,
    "JPY": 158.25,
}


def is_supported(currency: str | None) -> bool:
    """True for no currency, dollars, or a currency in the table."""
    return currency is None or currency.upper() == "USD" or currency.upper() in UNITS_PER_DOLLAR


def _plain_number(amount: float) -> str:
    """3000.0 is "3,000" and 19.5 is "19.50"."""
    return f"{amount:,.0f}" if amount == int(amount) else f"{amount:,.2f}"


def convert_search(spec: SearchSpec) -> tuple[SearchSpec, list[str]]:
    """The search with its price limits in whole dollars, plus one line per amount converted.

    Whole dollars, because the rate is only rough and the reply states this exact number.
    The line is what the reply repeats, for example "3,000 ILS is roughly $948".
    The currency must already be supported.
    """
    currency = spec.currency.upper() if spec.currency else "USD"
    if currency == "USD":
        return spec.model_copy(update={"currency": None}), []

    rate = UNITS_PER_DOLLAR[currency]
    update: dict[str, float | None] = {"currency": None}
    notes = []
    for field in ("price_min", "price_max"):
        amount = getattr(spec, field)
        if amount is not None:
            dollars = round(amount / rate)
            update[field] = dollars
            notes.append(f"{_plain_number(amount)} {currency} is roughly ${dollars:,}")
    return spec.model_copy(update=update), notes
