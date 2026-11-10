from datetime import UTC, datetime, timedelta
from decimal import Decimal
import json

import httpx
import pytest

from app.currency import CachedRateProvider, RateUnavailable, UnsupportedCurrency, convert_search
from app.schemas import SearchSpec


NOW = datetime(2026, 11, 9, 12, tzinfo=UTC)


def install_response(monkeypatch, *, status=200, **changes):
    calls = []
    data = {'base': 'USD', 'quote': 'ILS', 'date': '2026-11-09', 'rate': '3.1234567890123456789', **changes}

    def get(url, **kwargs):
        calls.append((url, kwargs))
        return httpx.Response(status, json=data, request=httpx.Request('GET', url))

    monkeypatch.setattr('app.currency.httpx.get', get)
    return calls


def unavailable(*args, **kwargs):
    raise httpx.ConnectTimeout('offline')


def test_fetch_is_exact_and_cache_survives_restart(monkeypatch, tmp_path):
    calls = install_response(monkeypatch)
    path = tmp_path / 'quotes.json'
    provider = CachedRateProvider(path, lambda: NOW)
    rate = provider.get_rate('ils')
    assert rate.units_per_usd == Decimal('3.1234567890123456789')
    assert rate.source == 'Frankfurter' and not rate.stale
    assert provider.get_rate('ILS') == rate
    assert CachedRateProvider(path, lambda: NOW).get_rate('ILS') == rate
    assert calls == [('https://api.frankfurter.dev/v2/rate/usd/ils', {'timeout': 5})]
    normalized, notes = convert_search(SearchSpec(price_max=300, currency='ILS'), rate)
    assert normalized.price_max == 96.04
    assert '2026-11-09' in notes[0] and 'Frankfurter' in notes[0]


def test_decimal_json_numbers_are_not_rounded_to_float(monkeypatch):
    response = httpx.Response(200, content=b'{"base":"USD","quote":"ILS","date":"2026-11-09","rate":3.1234567890123456789}',
                              request=httpx.Request('GET', 'https://example.com'))
    monkeypatch.setattr('app.currency.httpx.get', lambda *a, **k: response)
    assert CachedRateProvider(None, lambda: NOW).get_rate('ILS').units_per_usd == Decimal('3.1234567890123456789')


def test_hourly_refresh_and_bounded_outage_fallback(monkeypatch, tmp_path):
    now = [NOW]
    calls = install_response(monkeypatch)
    provider = CachedRateProvider(tmp_path / 'quotes.json', lambda: now[0])
    initial = provider.get_rate('ILS')
    now[0] += timedelta(hours=1)
    assert provider.get_rate('ILS').fetched_at == now[0]
    assert len(calls) == 2
    monkeypatch.setattr('app.currency.httpx.get', unavailable)
    now[0] += timedelta(hours=1)
    fallback = provider.get_rate('ILS')
    assert fallback.stale and fallback.units_per_usd == initial.units_per_usd
    _, notes = convert_search(SearchSpec(price_max=100, currency='ILS'), fallback)
    assert 'cached after refresh failure' in notes[0]
    now[0] = NOW + timedelta(days=8)
    with pytest.raises(RateUnavailable):
        provider.get_rate('ILS')


@pytest.mark.parametrize('changes', [
    {'rate': 0}, {'rate': -1}, {'rate': 'NaN'}, {'rate': 'Infinity'},
    {'base': 'EUR'}, {'quote': 'EUR'}, {'date': '2026-11-10'}, {'date': '2026-10-01'},
])
def test_invalid_or_old_quotes_are_rejected(monkeypatch, changes):
    install_response(monkeypatch, **changes)
    with pytest.raises(RateUnavailable):
        CachedRateProvider(None, lambda: NOW).get_rate('ILS')


@pytest.mark.parametrize('status', [404, 422])
def test_unsupported_pair_is_distinct_from_outage(monkeypatch, status):
    install_response(monkeypatch, status=status)
    with pytest.raises(UnsupportedCurrency):
        CachedRateProvider(None, lambda: NOW).get_rate('ZZZ')


def test_corrupt_cache_is_replaced_and_write_failure_is_nonfatal(monkeypatch, tmp_path):
    calls = install_response(monkeypatch)
    path = tmp_path / 'quotes.json'
    path.write_text('broken', encoding='utf-8')
    assert CachedRateProvider(path, lambda: NOW).get_rate('ILS').currency == 'ILS'
    assert json.loads(path.read_text())['version'] == 1
    monkeypatch.setattr('app.currency.os.replace', lambda *a: (_ for _ in ()).throw(OSError('disk full')))
    assert CachedRateProvider(tmp_path / 'other.json', lambda: NOW).get_rate('ILS').currency == 'ILS'
    assert len(calls) == 2


def test_usd_and_rating_only_need_no_quote_and_url_input_is_validated(monkeypatch):
    monkeypatch.setattr('app.currency.httpx.get', lambda *a, **k: pytest.fail('unexpected HTTP'))
    assert convert_search(SearchSpec(price_max=100))[0].price_max == 100
    assert convert_search(SearchSpec(currency='ILS', rating_min=4))[0].rating_min == 4
    with pytest.raises(UnsupportedCurrency):
        CachedRateProvider(None).get_rate('../secrets')
    with pytest.raises(RateUnavailable):
        convert_search(SearchSpec(currency='ILS', price_max=100))
