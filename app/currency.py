"""Fetch current published reference rates; keep conversion arithmetic in Python."""

from collections.abc import Callable
from datetime import UTC, datetime, timedelta
from decimal import Decimal, ROUND_CEILING, ROUND_FLOOR
from functools import lru_cache
import json
import logging
import math
import os
from pathlib import Path
import re
import tempfile
from threading import Lock
from typing import Protocol

import httpx

from app.config import ROOT
from app.observability import span
from app.schemas import CurrencyRate, SearchSpec

API_URL = "https://api.frankfurter.dev/v2/rate/usd"
CACHE_PATH = ROOT / "exchange_rates_cache.json"
CACHE_TTL = timedelta(hours=1)
MAX_CACHE_AGE = timedelta(days=7)
TIMEOUT_SECONDS = 5
logger = logging.getLogger(__name__)


class UnsupportedCurrency(ValueError):
    pass


class RateUnavailable(RuntimeError):
    """No usable quote is available; ask for a USD budget instead."""


class RateSource(Protocol):
    def get_rate(self, code: str) -> CurrencyRate: ...


def currency_code(value: str | None) -> str:
    code = (value or "USD").strip().upper()
    if not re.fullmatch(r"[A-Z]{3}", code):
        raise UnsupportedCurrency(code)
    return code


def needs_rate(spec: SearchSpec) -> bool:
    return (spec.price_min is not None or spec.price_max is not None) and currency_code(spec.currency) != "USD"


class CachedRateProvider:
    """An hourly local cache with a bounded, explicitly disclosed outage fallback."""

    def __init__(self, cache_path: Path | None = CACHE_PATH,
                 clock: Callable[[], datetime] | None = None):
        self.cache_path = cache_path
        self.clock = clock or (lambda: datetime.now(UTC))
        self._lock = Lock()
        self._rates: dict[str, CurrencyRate] | None = None

    def _read_cache(self) -> dict[str, CurrencyRate]:
        if self.cache_path is None:
            return {}
        try:
            data = json.loads(self.cache_path.read_text(encoding="utf-8"))
            if data["version"] != 1 or not isinstance(data["rates"], dict):
                return {}
            rates = {code: CurrencyRate.model_validate(value) for code, value in data["rates"].items()}
            return {code: rate for code, rate in rates.items() if code == rate.currency and rate.source == "Frankfurter"}
        except (OSError, ValueError, KeyError, TypeError):
            return {}

    def _write_cache(self) -> None:
        if self.cache_path is None:
            return
        temporary = None
        try:
            self.cache_path.parent.mkdir(parents=True, exist_ok=True)
            handle, temporary = tempfile.mkstemp(dir=self.cache_path.parent, suffix=".json")
            with os.fdopen(handle, "w", encoding="utf-8") as output:
                json.dump({"version": 1, "rates": {code: rate.model_dump(mode="json")
                          for code, rate in (self._rates or {}).items()}}, output)
            os.replace(temporary, self.cache_path)
        except OSError as error:
            logger.warning("Currency quotes remain usable but could not be cached: %s", type(error).__name__)
        finally:
            if temporary is not None:
                try:
                    Path(temporary).unlink(missing_ok=True)
                except OSError:
                    pass

    @staticmethod
    def _usable(rate: CurrencyRate, now: datetime) -> bool:
        return (timedelta(0) <= now - rate.fetched_at <= MAX_CACHE_AGE
                and timedelta(0) <= now.date() - rate.rate_date <= MAX_CACHE_AGE)

    def _fetch(self, code: str, now: datetime) -> CurrencyRate:
        response = httpx.get(f"{API_URL}/{code.lower()}", timeout=TIMEOUT_SECONDS)
        if response.status_code in (404, 422):
            raise UnsupportedCurrency(code)
        response.raise_for_status()
        data = response.json(parse_float=Decimal)
        if not isinstance(data, dict) or data.get("base") != "USD" or data.get("quote") != code:
            raise ValueError("currency response does not match the requested pair")
        rate = CurrencyRate(currency=code, units_per_usd=data["rate"], rate_date=data["date"],
                            fetched_at=now, source="Frankfurter")
        if not self._usable(rate, now):
            raise ValueError("currency response has a stale or future date")
        return rate

    def get_rate(self, code: str) -> CurrencyRate:
        code = currency_code(code)
        if code == "USD":
            raise ValueError("USD conversions use the identity rate without a fetch")
        with self._lock, span("currency_rate", {"base": "USD", "quote": code}) as run:
            if self._rates is None:
                self._rates = self._read_cache()
            now = self.clock()
            cached = self._rates.get(code)
            usable = cached is not None and self._usable(cached, now)
            if usable and now - cached.fetched_at < CACHE_TTL:
                rate = cached
                status = "cache_hit"
            else:
                try:
                    rate = self._fetch(code, now)
                except UnsupportedCurrency:
                    raise
                except (httpx.HTTPError, ValueError, KeyError, TypeError) as error:
                    if not usable:
                        raise RateUnavailable("No current or recent cached reference rate") from error
                    rate = cached.model_copy(update={"stale": True})
                    status = "cached_after_refresh_failure"
                else:
                    self._rates[code] = rate
                    self._write_cache()
                    status = "fetched"
            if run is not None:
                run.end(outputs={"status": status, "rate": rate.model_dump(mode="json")})
            return rate


@lru_cache(maxsize=1)
def get_rate_provider() -> CachedRateProvider:
    return CachedRateProvider()


def cent_bound(value: Decimal, minimum: bool, strict: bool) -> float:
    cents = value * 100
    if minimum:
        integer = cents.to_integral_value(rounding=ROUND_FLOOR) + 1 if strict else cents.to_integral_value(rounding=ROUND_CEILING)
    else:
        integer = cents.to_integral_value(rounding=ROUND_CEILING) - 1 if strict else cents.to_integral_value(rounding=ROUND_FLOOR)
    result = float(integer / 100)
    if not math.isfinite(result):
        raise ValueError("converted limit is not finite")
    return result


def convert_search(spec: SearchSpec, rate: CurrencyRate | None = None) -> tuple[SearchSpec, list[str]]:
    """Pure conversion: the caller supplies the exact quote used for this search."""
    required = needs_rate(spec)
    code = currency_code(spec.currency) if required else "USD"
    if required and (rate is None or rate.currency != code):
        raise RateUnavailable("A matching reference rate is required")
    units = rate.units_per_usd if required else Decimal(1)
    changes = {"currency": "USD", "price_min_strict": False, "price_max_strict": False,
               "rating_min_strict": False}
    notes = []
    for field in ("price_min", "price_max"):
        amount = getattr(spec, field)
        if amount is None:
            continue
        converted = cent_bound(Decimal(str(amount)) / units, field == "price_min",
                               bool(getattr(spec, field + "_strict")))
        changes[field] = converted
        if required:
            term = spec.currency_term or code
            status = "; cached after refresh failure" if rate.stale else ""
            notes.append(f"{amount:,.2f} {term} ≈ ${converted:,.2f} ({rate.source}; {rate.rate_date}; conversation rate{status})")
    if spec.rating_min is not None:
        changes["rating_min"] = cent_bound(Decimal(str(spec.rating_min)), True, bool(spec.rating_min_strict))
    return spec.model_copy(update=changes), notes
