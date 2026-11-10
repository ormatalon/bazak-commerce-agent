import pytest

from app import catalog
from app.config import RetrievalConfig


def test_category_text_cannot_masquerade_as_a_slug_list():
    raw={'products':[{'id':1,'title':'Product','category':'x','price':1,'rating':4}],'categories':'xyz'}
    with pytest.raises(ValueError):
        catalog._parse(raw)


def test_catalog_snapshot_checks_ids_and_membership():
    product={'id':1,'title':'Product','category':'test','price':1,'rating':4}
    with pytest.raises(ValueError):
        catalog._parse({'products':[product,product],'categories':['test']})
    with pytest.raises(ValueError):
        catalog._parse({'products':[product],'categories':['other']})


@pytest.mark.parametrize('settings',[{'strong_threshold':float('nan')},{'category_boost':float('inf')},{'candidate_window':0}])
def test_invalid_ranking_configuration_is_rejected(settings):
    with pytest.raises(ValueError):
        RetrievalConfig(**settings)
