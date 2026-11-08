"""Shared data models. Every module builds against these, and only the Lead edits them."""

from collections.abc import Callable
from typing import Any, Literal

from pydantic import (
    BaseModel,
    ConfigDict,
    Field,
    ValidationInfo,
    field_validator,
    model_validator,
)

Intent = Literal["product_search", "needs_clarification", "off_catalog", "small_talk"]
Mode = Literal["new", "refine", "show_more"]
ClearableField = Literal[
    "keywords", "exclude_keywords", "category", "price_min", "price_max", "rating_min",
    "sort_by", "order", "top_k",
]

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

    Bounds are inclusive. On a refine, null means "keep the previous value", so
    keywords is nullable too: an empty list would wipe them. Defaults are None or
    default_factory so the strict structured-output schema carries no default keys.
    """

    keywords: list[str] | None = None
    # Words for what the shopper does not want ("not Apple", "no iPhones", "without heels").
    # A product with one in its title, brand or tags is dropped: a hard filter that the
    # fallback never loosens. Null on a refine means keep.
    exclude_keywords: list[str] | None = None
    category: str | None = None
    price_min: float | None = None
    price_max: float | None = None
    # No upper limit: "rated above 5" is valid input and must reach the fallback.
    rating_min: float | None = None
    sort_by: Literal["price", "rating"] | None = None
    order: Literal["asc", "desc"] | None = None
    # Checked in a validator, not Field(gt=0), to keep exclusiveMinimum out of the schema.
    top_k: int | None = None
    # True when the shopper asks to see all of a kind. A separate field, because "top_k"
    # is a number the shopper stated and the evals compare it. Null on a refine means keep.
    show_all: bool | None = None
    # Set by the model when the budget is not in dollars. The parser converts the price
    # limits to dollars and clears this, so no other code ever sees another currency.
    currency: str | None = None
    # Which previous search a refine edits; None means the first.
    refines_index: int | None = None
    clear_fields: list[ClearableField] = Field(default_factory=list)

    @field_validator("category")
    @classmethod
    def category_is_known(cls, value: str | None, info: ValidationInfo) -> str | None:
        """Check against the real slugs, which are only known once the catalog loads.

        Pass them with SearchSpec.model_validate(data, context={"categories": slugs}).
        Without that context nothing is checked, which lets tests build specs directly.
        parse_request must always pass it.
        """
        categories = (info.context or {}).get("categories")
        if value is not None and categories is not None and value not in categories:
            raise ValueError(f"unknown category: {value}")
        return value

    @field_validator("top_k")
    @classmethod
    def top_k_is_positive(cls, value: int | None) -> int | None:
        if value is not None and value < 1:
            raise ValueError("top_k must be at least 1")
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
    # On needs_clarification: the categories the request could mean, for the reply to offer.
    category_options: list[str] = Field(default_factory=list)
    # Written by code, not the model: one line per amount converted to dollars.
    conversions: list[str] = Field(default_factory=list)

    @model_validator(mode="before")
    @classmethod
    def only_product_search_has_a_search(cls, data: Any) -> Any:
        """Drop stray search fields, so an off-catalog request can never show cards.

        Runs before field validation: an invented slug in a stray search would
        otherwise raise, turning a correct decline into the safe default.
        """
        if isinstance(data, dict) and data.get("intent") != "product_search":
            return {**data, "mode": None, "searches": []}
        return data


class SearchOutcome(BaseModel):
    """The result of one search, after any fallback."""

    # The merged search as the user asked for it, before loosening, so the reply
    # can still say "nothing under $10".
    spec: SearchSpec
    # Everything that matched, ranked, with no display cap.
    products: list[Product] = Field(default_factory=list)
    # The cards to display. The pipeline fills this; the responder may only mention these.
    shown: list[Product] = Field(default_factory=list)
    # How many products fit the search, for "how many do you have?". The pipeline fills this.
    total: int = 0
    # In the order they were loosened, so the reply can say what changed.
    loosened: list[Literal["rating", "price"]] = Field(default_factory=list)


class ChatTurn(BaseModel):
    """One history entry passed to the parser."""

    role: Literal["user", "assistant"]
    text: str


class ConversationState(BaseModel):
    """What a conversation carries between turns. Storage saves and restores this."""

    history: list[ChatTurn] = Field(default_factory=list)
    # The most recent searches, even if small talk came after them.
    searches: list[SearchSpec] = Field(default_factory=list)
    # Products shown for those searches, which show_more excludes.
    shown: list[Product] = Field(default_factory=list)


class TurnResult(BaseModel):
    """Everything one turn produced, for the UI, the flow test and the evals."""

    parsed: ParsedRequest
    outcomes: list[SearchOutcome] = Field(default_factory=list)
    reply: str
    state: ConversationState
