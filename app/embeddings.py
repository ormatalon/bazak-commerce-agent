"""Local multilingual E5 adapter, with explicit query/passage formatting."""

from collections.abc import Sequence
import os

import numpy as np

from app.config import ROOT, RetrievalConfig
from app.observability import span


class LocalEmbedder:
    def __init__(self, config: RetrievalConfig, download: bool = False):
        # Keep downloads in the workspace. Offline is the normal runtime mode.
        os.environ.setdefault("HF_HOME", str(ROOT / ".models"))
        from sentence_transformers import SentenceTransformer
        self.config = config
        self.model = SentenceTransformer(config.model, revision=config.revision,
                                        cache_folder=str(ROOT / ".models"),
                                        local_files_only=not download, device="cpu")
        self.model.max_seq_length = 512

    def encode(self, texts: Sequence[str], query: bool = False) -> np.ndarray:
        prefix = "query: " if query else "passage: "
        with span("query_embedding" if query else "document_embedding", {"count": len(texts)},
                  {"model": self.config.model, "revision": self.config.revision}):
            return np.asarray(self.model.encode([prefix + text for text in texts],
                              normalize_embeddings=True, show_progress_bar=False,
                              batch_size=32), dtype=np.float32)


def main() -> None:
    import argparse
    parser = argparse.ArgumentParser(description="Download the pinned local embedding model.")
    parser.add_argument("--download", action="store_true", help="Allow the first model download.")
    args = parser.parse_args()
    embedder = LocalEmbedder(RetrievalConfig(), download=args.download)
    print(f"Embedding model ready: {embedder.config.model}@{embedder.config.revision}")


if __name__ == "__main__":
    main()
