import numpy as np

from app.index import ProductIndex
from app.schemas import Product


class Embedder:
    calls = 0

    def encode(self, texts, query=False):
        self.calls += 1
        return np.asarray([[1.0, 0.0] for _ in texts], dtype=np.float32)


def product(identifier=1):
    return Product(id=identifier, title="Laptop", category="laptops", price=100, rating=4)


def test_cache_reuse_and_product_identity(tmp_path):
    path = tmp_path / "index.npz"
    embedder = Embedder()
    index = ProductIndex([product()], embedder, cache=path)
    assert not index.cache_hit and embedder.calls == 2
    assert ProductIndex([product()], embedder, cache=path).cache_hit
    assert embedder.calls == 2
    assert not ProductIndex([product(2)], embedder, cache=path).cache_hit
    assert embedder.calls == 4


def test_corrupt_cache_rebuilds_and_weighted_cosine(tmp_path):
    path = tmp_path / "index.npz"
    path.write_bytes(b"damaged")
    index = ProductIndex([product()], Embedder(), cache=path)
    index.descriptions = np.asarray([[0.0, 1.0]], dtype=np.float32)
    assert np.allclose(index.similarities(np.asarray([1.0, 0.0])), [0.6])


def test_wrong_metadata_shape_is_a_cache_miss(tmp_path):
    path = tmp_path/'index.npz'
    np.savez(path,metadata='[]',titles=np.asarray([[1.,0.]]),descriptions=np.asarray([[1.,0.]]))
    index = ProductIndex([product()],Embedder(),cache=path)
    assert not index.cache_hit


def test_cache_write_failure_keeps_the_index_usable(tmp_path,monkeypatch):
    def denied(*args):
        raise PermissionError('read-only cache')
    monkeypatch.setattr(ProductIndex,'_write',denied)
    index = ProductIndex([product()],Embedder(),cache=tmp_path/'index.npz')
    assert np.allclose(index.similarities(np.asarray([1.,0.])),[1.])
