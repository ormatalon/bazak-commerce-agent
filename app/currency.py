"""Convert stated constraints once, in code, with dated snapshot rates."""

from decimal import Decimal, ROUND_CEILING, ROUND_FLOOR

from app.schemas import SearchSpec

RATES_DATE = "2026-11-04"
UNITS_PER_DOLLAR = {
    "AUD": "1.4255", "CAD": "1.3935", "CHF": "0.81548", "EUR": "0.88755",
    "GBP": "0.74075", "ILS": "3.1633", "JPY": "158.25", "USD": "1",
}


class UnsupportedCurrency(ValueError):
    pass


def cent_bound(value: Decimal, minimum: bool, strict: bool) -> float:
    cents = value * 100
    if minimum:
        integer = cents.to_integral_value(rounding=ROUND_FLOOR) + 1 if strict else cents.to_integral_value(rounding=ROUND_CEILING)
    else:
        integer = cents.to_integral_value(rounding=ROUND_CEILING) - 1 if strict else cents.to_integral_value(rounding=ROUND_FLOOR)
    return float(integer / 100)


def convert_search(spec: SearchSpec) -> tuple[SearchSpec, list[str]]:
    code = (spec.currency or "USD").upper()
    if code not in UNITS_PER_DOLLAR:
        raise UnsupportedCurrency(code)
    rate = Decimal(UNITS_PER_DOLLAR[code])
    changes = {"currency": "USD", "price_min_strict": False, "price_max_strict": False,
               "rating_min_strict": False}
    notes = []
    for field in ("price_min", "price_max"):
        amount = getattr(spec, field)
        if amount is None:
            continue
        converted = cent_bound(Decimal(str(amount)) / rate, field == "price_min",
                               bool(getattr(spec, field + "_strict")))
        changes[field] = converted
        if code != "USD":
            term = spec.currency_term or code
            notes.append(f"{amount:,.2f} {term} ≈ ${converted:,.2f} ({RATES_DATE})")
    if spec.rating_min is not None:
        changes["rating_min"] = cent_bound(Decimal(str(spec.rating_min)), True, bool(spec.rating_min_strict))
    # A strict maximum of zero legitimately produces -0.01 and matches nothing.
    # model_copy preserves this normalized bound without revalidating source amounts.
    return spec.model_copy(update=changes), notes
