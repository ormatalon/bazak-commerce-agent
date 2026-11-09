from decimal import Decimal
import pytest

import numpy as np

from app.config import RetrievalConfig
from app.currency import cent_bound, convert_search
from app.index import ProductIndex
from app.parser import merge_searches
from app.schemas import Direction, ParsedRequest, Product, SearchSpec
from app.search import rank_all, search


class Embedder:
    def encode(self, texts, query=False):
        return np.asarray([[1., 0.] for _ in texts], dtype=np.float32)


def test_currency_strict_boundary_applied_after_conversion():
    assert cent_bound(Decimal('1.234'), False, True) == 1.23
    assert cent_bound(Decimal('1.23'), False, True) == 1.22
    assert cent_bound(Decimal('1.23'), True, True) == 1.24
    original = SearchSpec(price_max=3000, currency='ILS', currency_term='NIS')
    converted, notes = convert_search(original)
    assert converted.price_max == 948.37
    assert original.price_max == 3000 and 'NIS' in notes[0]


def test_refinement_keeps_other_requests_and_limits():
    old = [SearchSpec(price_max=50), SearchSpec(price_max=100)]
    parsed = ParsedRequest(intent='product_search', mode='refine', searches=[SearchSpec(refines_index=1, rating_min=4)])
    merged = merge_searches(parsed, old)
    assert merged[0].price_max == 50
    assert merged[1].price_max == 100 and merged[1].rating_min == 4
    assert old[1].rating_min is None


def test_exclusion_plural_matches_singular_without_substring_overreach():
    from app.search import excluded
    phone = Product(id=1, title='iPhone 6', category='smartphones', price=100, rating=4)
    watch = Product(id=2, title='Wrist Watch', category='watches', price=100, rating=4)
    assert excluded(phone, ['iPhones'])
    assert excluded(watch, ['watches'])
    assert not excluded(phone, ['phone case'])


def test_wrong_category_strong_match_and_zero_variance():
    products = [Product(id=i, title=f'Product {i}', category='laptops', price=i, rating=4) for i in range(1, 16)]
    index = ProductIndex(products, Embedder(), config=RetrievalConfig(strong_threshold=1.5, borderline_threshold=0.5), cache=None)
    spec = SearchSpec(directions=[Direction(query='laptop', categories=['tablets'])])
    assert search(spec, index) == []  # all equal is uninformative
    index.similarities = lambda vector: np.asarray([1.] + [0.] * 14)
    candidates = search(spec, index)
    assert [c.product.id for c in candidates] == [1]
    assert candidates[0].zone == 'strong'


def test_refinement_cannot_reinterpret_retained_currency_bound():
    from app.parser import CurrencyRefinementError, merge_refine
    base = SearchSpec(price_min=1000,price_max=3000,currency='ILS',currency_term='NIS')
    with pytest.raises(CurrencyRefinementError):
        merge_refine(base,SearchSpec(price_max=500,currency='USD'))
    assert base.price_min == 1000 and base.currency == 'ILS'
    changed = merge_refine(base,SearchSpec(price_min=100,price_max=500,currency='USD'))
    assert changed.currency_term is None and changed.price_min == 100


def test_explicit_count_replaces_show_all_and_sort_clear_removes_order():
    from app.parser import merge_refine
    changed = merge_refine(SearchSpec(show_all=True,sort_by='price',order='desc'),
                           SearchSpec(top_k=1,clear_fields=['sort_by']))
    assert changed.top_k == 1 and changed.show_all is False
    assert changed.sort_by is None and changed.order is None
    all_products = merge_refine(SearchSpec(top_k=1),SearchSpec(show_all=True))
    assert all_products.show_all is True and all_products.top_k is None
