"""Shared data models. Every module builds against these, and only the Lead edits them."""

from collections.abc import Callable
from typing import Literal

from pydantic import BaseModel, ConfigDict, Field, ValidationInfo, field_validator

Intent = Literal["product_search", "needs_clarification", "off_catalog", "small_talk"]
Mode = Literal["new", "refine", "show_more"]

# Tests pass a fake, so nothing outside app/llm.py needs the OpenAI client.
# Takes chat messages and an optional output schema, returns the model's raw text.
LLM = Callable[[list[dict[str, str]], type[BaseModel] | None], str]


class Product(BaseModel):
    """One catalog product, keeping only the fields the app can show or answer from."""

    model_config = ConfigDict(extra="ignore", populate_by_name=True)

    id: int
    title: str
    description: str
    category: str
    price: float
    rating: float
    tags: list[str] = Field(default_factory=list)
    brand: str | None = None
    thumbnail: str = ""
    availability: str | None = Field(default=None, alias="availabilityStatus")
    warranty: str | None = Field(default=None, alias="warrantyInformation")
    shipping: str | None = Field(default=None, alias="shippingInformation")
    return_policy: str | None = Field(default=None, alias="returnPolicy")


class SearchSpec(BaseModel):
    """One structured search. Field names match datasets/deterministic.csv.

    Bounds are inclusive. On a refine, null means "keep the previous value".
    Lists use default_factory and nullable fields default to None because
    OpenAI's strict structured output rejects other defaults in the schema.
    """

    keywords: list[str] = Field(default_factory=list)
    category: str | None = None
    price_min: float | None = None
    price_max: float | None = None
    # No upper limit: "rated above 5" is valid input and must reach the fallback.
    rating_min: float | None = None
    sort_by: Literal["price", "rating"] | None = None
    order: Literal["asc", "desc"] | None = None
    top_k: int | None = Field(default=None, gt=0)
    # Which previous search a refine edits; None means the first.
    refines_index: int | None = None
    clear_fields: list[str] = Field(default_factory=list)

    @field_validator("category")
    @classmethod
    def category_is_known(cls, value: str | None, info: ValidationInfo) -> str | None:
        """Check against the real slugs, which are only known once the catalog loads.

        Pass them with SearchSpec.model_validate(data, context={"categories": slugs}).
        """
        categories = (info.context or {}).get("categories")
        if value is not None and categories is not None and value not in categories:
            raise ValueError(f"unknown category: {value}")
        return value


class ParsedRequest(BaseModel):
    """What the parser understood from one user message. The user never sees it."""

    intent: Intent
    # Set only for product_search.
    mode: Mode | None = None
    # Empty unless the intent is product_search; more than one means multi-intent.
    searches: list[SearchSpec] = Field(default_factory=list)
    # What we can't do, e.g. "book a flight", so a mixed request can still show products.
    unsupported: list[str] = Field(default_factory=list)


class SearchOutcome(BaseModel):
    """The result of one search, after any fallback."""

    spec: SearchSpec
    products: list[Product] = Field(default_factory=list)
    # In the order they were loosened, so the reply can say what changed.
    loosened: list[Literal["rating", "price"]] = Field(default_factory=list)


class ChatTurn(BaseModel):
    """One history entry passed to the parser."""

    role: Literal["user", "assistant"]
    text: str
