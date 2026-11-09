"""Shared contracts for parsing, retrieval, UI, persistence, and evaluation."""

from collections.abc import Callable
from typing import Any, Literal

from pydantic import BaseModel, ConfigDict, Field, ValidationInfo, field_validator, model_validator


class Model(BaseModel):
    model_config = ConfigDict(extra="forbid", allow_inf_nan=False)


class Product(BaseModel):
    model_config = ConfigDict(extra="ignore", allow_inf_nan=False)
    id: int
    title: str
    description: str = ""
    category: str
    price: float = Field(ge=0)
    rating: float
    tags: list[str] = Field(default_factory=list)
    brand: str | None = None
    thumbnail: str = ""


class Direction(Model):
    query: str = Field(min_length=1)
    categories: list[str] = Field(default_factory=list)

    @field_validator("query")
    @classmethod
    def nonempty_query(cls, value: str) -> str:
        if not value.strip():
            raise ValueError("query must contain text")
        return value.strip()

    @field_validator("categories")
    @classmethod
    def known_categories(cls, value: list[str], info: ValidationInfo) -> list[str]:
        known = (info.context or {}).get("categories")
        if known is not None and any(slug not in known for slug in value):
            raise ValueError("unknown category")
        return list(dict.fromkeys(value))


class SearchSpec(Model):
    """One request; directions are alternatives, searches are independent requests.

    Price values remain in the original currency in saved state. Currency conversion
    produces a separate copy for retrieval. Null means keep during a refinement.
    """

    directions: list[Direction] | None = None
    exclude: list[str] | None = None
    price_min: float | None = Field(default=None, ge=0)
    price_max: float | None = Field(default=None, ge=0)
    price_min_strict: bool | None = Field(default=None, description="True only when price_min is an exclusive lower bound (over/above a price).")
    price_max_strict: bool | None = Field(default=None, description="True only when price_max is an exclusive upper bound (under/below a price).")
    rating_min: float | None = None
    rating_min_strict: bool | None = Field(default=None, description="True only when rating_min is an exclusive lower rating bound.")
    currency: str | None = None
    currency_term: str | None = None
    sort_by: Literal["price", "rating"] | None = None
    order: Literal["asc", "desc"] | None = None
    top_k: int | None = Field(default=None, ge=1, description="Explicit count, including a singular superlative request (1); otherwise null.")
    show_all: bool | None = None
    vague: bool | None = None
    refines_index: int | None = Field(default=None, ge=0)
    clear_fields: list[Literal[
        "directions", "exclude", "price_min", "price_max", "rating_min",
        "currency", "sort_by", "order", "top_k", "show_all",
    ]] = Field(default_factory=list)

    @model_validator(mode="after")
    def sensible_request(self) -> "SearchSpec":
        if self.show_all and self.top_k is not None:
            raise ValueError("choose an explicit count or all products, not both")
        for field in ("price_min", "price_max", "rating_min"):
            if getattr(self, field + "_strict") and getattr(self, field) is None:
                raise ValueError("a strict operator requires its corresponding bound")
        if self.price_min is not None and self.price_max is not None:
            if self.price_min > self.price_max:
                raise ValueError("minimum price exceeds maximum")
            if self.price_min == self.price_max and (self.price_min_strict or self.price_max_strict):
                raise ValueError("empty price interval")
        if self.directions is not None:
            if len(self.directions) > 3 or any(not d.query.strip() for d in self.directions):
                raise ValueError("provide up to three nonempty query directions")
        return self


class ParsedRequest(Model):
    intent: Literal["product_search", "needs_clarification", "off_catalog", "small_talk"]
    mode: Literal["new", "refine", "show_more"] | None = None
    searches: list[SearchSpec] = Field(default_factory=list)
    unsupported: list[str] = Field(default_factory=list)

    @model_validator(mode="before")
    @classmethod
    def valid_intent(cls, data: Any) -> Any:
        if isinstance(data, dict):
            # Discard stray searches before validating nested category guesses.
            if data.get("intent") != "product_search":
                return {**data, "searches": [], "mode": None}
            if data.get("mode") is None:
                raise ValueError("product search requires a mode")
        return data


class Candidate(Model):
    product: Product
    direction: int
    similarity: float
    z_score: float
    category_boost: float
    score: float
    zone: Literal["strong", "borderline", "weak", "uninformative"]
    relevant: bool
    reason: str
    type_compatible: bool | None = None


class Relaxation(Model):
    field: Literal["rating_min", "price_min", "price_max"]
    original: float
    actual: float


class Card(Model):
    product: Product
    alternative: bool = False
    relaxations: list[Relaxation] = Field(default_factory=list)


class SearchOutcome(Model):
    spec: SearchSpec
    candidates: list[Candidate] = Field(default_factory=list)
    cards: list[Card] = Field(default_factory=list)
    exact_ids: list[int] = Field(default_factory=list)
    total: int = 0
    has_more: bool = False
    reason: str = "exact"
    conversions: list[str] = Field(default_factory=list)

    @property
    def shown(self) -> list[Product]:
        return [card.product for card in self.cards]


class ChatTurn(Model):
    role: Literal["user", "assistant"]
    text: str


class ConversationState(Model):
    history: list[ChatTurn] = Field(default_factory=list)
    searches: list[SearchSpec] = Field(default_factory=list)
    shown: list[Product] = Field(default_factory=list)


class TurnResult(Model):
    parsed: ParsedRequest
    outcomes: list[SearchOutcome] = Field(default_factory=list)
    reply: str
    state: ConversationState
    trace_id: str | None = None
    trace_context: dict[str, str] = Field(default_factory=dict)
    timings: dict[str, float] = Field(default_factory=dict)
    error: str | None = None


LLM = Callable[[list[dict[str, str]], type[BaseModel] | None], str]
