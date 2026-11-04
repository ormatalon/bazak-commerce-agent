"""Chainlit entry point. Run with: chainlit run app/main.py"""

import json
import sys
from pathlib import Path

# chainlit run only puts app/ on the import path, so `from app...` needs the repo root.
sys.path.insert(0, str(Path(__file__).resolve().parent.parent))

import chainlit as cl  # noqa: E402

from app.schemas import Product  # noqa: E402

# The fields the card element reads (public/elements/ProductCards.jsx).
CARD_FIELDS = {"id", "title", "description", "price", "rating", "brand", "thumbnail", "category"}
SAMPLE_CATALOG = Path(__file__).resolve().parent.parent / "tests" / "fixtures" / "catalog_sample.json"


@cl.on_message
async def on_message(message: cl.Message) -> None:
    """TEMPORARY (wave 2): answer any message with 3 sample cards so the cards can be
    checked in a browser. Wave 3 replaces this with the real pipeline."""
    with open(SAMPLE_CATALOG, encoding="utf-8") as f:
        sample = [Product.model_validate(raw) for raw in json.load(f)[:3]]
    products = [p.model_dump(include=CARD_FIELDS) for p in sample]
    cards = cl.CustomElement(name="ProductCards", props={"products": products})
    await cl.Message(content="Here are 3 sample products.", elements=[cards]).send()
