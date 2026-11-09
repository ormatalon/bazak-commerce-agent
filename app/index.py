"""Two vectors per product, cached atomically with strict identity checks."""

from dataclasses import asdict
import json
import logging
import os
from pathlib import Path
import tempfile
from time import perf_counter

import numpy as np

from app.config import ROOT, RetrievalConfig, catalog_hash
from app.observability import span
from app.schemas import Product

logger = logging.getLogger(__name__)


def product_texts(product: Product) -> tuple[str, str]:
    title = " | ".join(s for s in [product.title, product.category.replace("-", " "), product.brand] if s)
    description = " | ".join(s for s in [product.description, ", ".join(product.tags)] if s)
    return title, description or product.title


class ProductIndex:
    def __init__(self, products: list[Product], embedder, config: RetrievalConfig | None = None,
                 cache: Path | None = ROOT / "embedding_cache.npz"):
        self.products = products
        self.embedder = embedder
        self.config = config or RetrievalConfig()
        if not products or len({p.id for p in products}) != len(products):
            raise ValueError("index requires nonempty products with unique IDs")
        self.identity = {"catalog_hash": catalog_hash(products), "ids": [p.id for p in products],
                         "model": self.config.model, "revision": self.config.revision,
                         "text_version": self.config.text_version, "normalized": True}
        started = perf_counter()
        self.cache_hit = cache is not None and self._read(cache)
        with span("index_startup", metadata={**self.identity, "cache_hit": self.cache_hit}):
            if not self.cache_hit:
                texts = [product_texts(p) for p in products]
                self.titles = embedder.encode([t[0] for t in texts])
                self.descriptions = embedder.encode([t[1] for t in texts])
                self._validate()
                if cache is not None:
                    self._write(cache)
        self.build_ms = (perf_counter() - started) * 1000
        logger.info("Index %s: %d products, %.0f ms", "cache hit" if self.cache_hit else "rebuilt", len(products), self.build_ms)

    def _validate(self) -> None:
        if self.titles.ndim != 2 or self.titles.shape != self.descriptions.shape or self.titles.shape[0] != len(self.products):
            raise ValueError("invalid index dimensions")
        if self.titles.shape[1] < 1 or not np.isfinite(self.titles).all() or not np.isfinite(self.descriptions).all():
            raise ValueError("invalid index values")
        if not np.allclose(np.linalg.norm(self.titles, axis=1), 1, atol=1e-4) or not np.allclose(np.linalg.norm(self.descriptions, axis=1), 1, atol=1e-4):
            raise ValueError("embedding vectors must be normalized")

    def _read(self, path: Path) -> bool:
        try:
            with np.load(path, allow_pickle=False) as data:
                metadata = json.loads(str(data["metadata"].item()))
                dimension = metadata.pop("dimension")
                if metadata != self.identity:
                    return False
                self.titles = data["titles"]
                self.descriptions = data["descriptions"]
                self._validate()
                return self.titles.shape[1] == dimension
        except (OSError, ValueError, KeyError, EOFError):
            return False

    def _write(self, path: Path) -> None:
        path.parent.mkdir(parents=True, exist_ok=True)
        handle, temporary = tempfile.mkstemp(dir=path.parent, suffix=".npz")
        os.close(handle)
        try:
            np.savez_compressed(temporary, titles=self.titles, descriptions=self.descriptions,
                                metadata=json.dumps({**self.identity, "dimension": self.titles.shape[1]}, sort_keys=True))
            os.replace(temporary, path)
        finally:
            Path(temporary).unlink(missing_ok=True)

    def similarities(self, query_vector: np.ndarray) -> np.ndarray:
        weight = self.config.title_weight
        vector = np.asarray(query_vector, dtype=np.float32)
        if vector.shape != (self.titles.shape[1],) or not np.isfinite(vector).all():
            raise ValueError("query vector does not match index")
        return weight * (self.titles @ vector) + (1 - weight) * (self.descriptions @ vector)
