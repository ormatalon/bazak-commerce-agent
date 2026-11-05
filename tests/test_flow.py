"""One message from input through a fake model and search to the card data sent to the UI.

The fake LLM only plays the parser. `write_reply` is replaced by a fake that records
what it was given, because the real one is another module's job. Nothing here calls a model.
"""

import json
from pathlib import Path

import pytest

import app.pipeline as pipeline
from app.pipeline import CARDS_PER_SEARCH, card_props, has_more, run_turn, show_more
from app.schemas import (
    ChatTurn,
    ConversationState,
    ParsedRequest,
    Product,
    SearchSpec,
)

FIXTURE = Path(__file__).parent / "fixtures" / "catalog_sample.json"
CATALOG = [Product.model_validate(raw) for raw in json.loads(FIXTURE.read_text(encoding="utf-8"))]
CATEGORIES = sorted({p.category for p in CATALOG})


def fake_llm_returning(parsed: ParsedRequest):
    """A fake LLM that always answers with this parse, as the model's raw JSON text."""

    def llm(messages, response_model=None):
        return parsed.model_dump_json()

    return llm


class ReplyRecorder:
    """Stands in for write_reply: remembers its arguments and returns a fixed reply."""

    def __init__(self) -> None:
        self.calls: list[tuple] = []

    def __call__(self, message, parsed, outcomes, llm):
        self.calls.append((message, parsed, outcomes))
        return "fake reply"


@pytest.fixture
def recorder(monkeypatch) -> ReplyRecorder:
    fake = ReplyRecorder()
    monkeypatch.setattr(pipeline, "write_reply", fake)
    return fake


def search_parse(*searches: SearchSpec, mode="new") -> ParsedRequest:
    return ParsedRequest(intent="product_search", mode=mode, searches=list(searches))


def turn(message: str, parsed: ParsedRequest, state: ConversationState | None = None):
    return run_turn(message, state or ConversationState(), CATALOG, CATEGORIES, fake_llm_returning(parsed))


def shown_ids(result) -> list[int]:
    return [p.id for o in result.outcomes for p in o.shown]


# --- new search ---------------------------------------------------------------


def test_new_search_shows_three_cards_and_keeps_all_matches(recorder):
    result = turn("phones", search_parse(SearchSpec(category="smartphones")))

    outcome = result.outcomes[0]
    assert len(outcome.shown) == CARDS_PER_SEARCH == 3
    assert len(outcome.products) == 16  # every match is kept, only the cards are capped
    assert outcome.shown == outcome.products[:3]
    assert result.reply == "fake reply"
    assert result.state.shown == outcome.shown
    assert result.state.searches == [SearchSpec(category="smartphones")]


def test_top_k_overrides_the_default_card_count(recorder):
    result = turn("top 5 phones", search_parse(SearchSpec(category="smartphones", top_k=5)))
    assert len(result.outcomes[0].shown) == 5

    result = turn("the cheapest tablet", search_parse(SearchSpec(category="tablets", sort_by="price", top_k=1)))
    assert [p.title for p in result.outcomes[0].shown] == ["Samsung Galaxy Tab White"]


def test_two_searches_make_two_outcomes(recorder):
    result = turn(
        "a laptop and sunglasses",
        search_parse(SearchSpec(category="laptops"), SearchSpec(category="sunglasses")),
    )
    assert len(result.outcomes) == 2
    assert {p.category for p in result.outcomes[0].shown} == {"laptops"}
    assert {p.category for p in result.outcomes[1].shown} == {"sunglasses"}
    assert len(result.state.shown) == 6


def test_the_reply_writer_gets_the_parse_and_the_outcomes(recorder):
    parsed = search_parse(SearchSpec(category="laptops"))
    result = turn("laptops", parsed)
    message, got_parsed, got_outcomes = recorder.calls[0]
    assert message == "laptops"
    assert got_parsed == parsed
    assert got_outcomes == result.outcomes


# --- which products get a card ---------------------------------------------------


def product(product_id: int, title: str, category: str = "gear", price: float = 10.0, rating: float = 4.0) -> Product:
    return Product(id=product_id, title=title, description="", category=category, price=price, rating=rating)


# Two hats and three scarves in one category. The scarves have the higher ratings, so the
# rating alone would put them first.
GEAR = [
    product(1, "Wool Hat", rating=3.0, price=30.0),
    product(2, "Straw Hat", rating=3.5, price=20.0),
    product(3, "Silk Scarf", rating=4.9),
    product(4, "Cotton Scarf", rating=4.8),
    product(5, "Linen Scarf", rating=4.7),
]


def gear_turn(spec: SearchSpec, state: ConversationState | None = None):
    return run_turn("gear", state or ConversationState(), GEAR, ["gear"], fake_llm_returning(search_parse(spec)))


def test_only_products_matching_a_keyword_get_cards_when_any_match(recorder):
    outcome = gear_turn(SearchSpec(category="gear", keywords=["hat"])).outcomes[0]
    assert [p.id for p in outcome.shown] == [2, 1]
    assert outcome.total == 2
    assert len(outcome.products) == 5  # search still finds all of them


def test_a_keyword_matching_nothing_shows_the_category(recorder):
    outcome = gear_turn(SearchSpec(category="gear", keywords=["gloves"])).outcomes[0]
    assert [p.id for p in outcome.shown] == [3, 4, 5]
    assert outcome.total == 5


def test_a_requested_sort_applies_among_the_matching_products(recorder):
    spec = SearchSpec(category="gear", keywords=["hat"], sort_by="price", order="asc", top_k=1)
    assert [p.id for p in gear_turn(spec).outcomes[0].shown] == [2]


def test_show_more_gives_the_matches_first_and_then_the_rest_of_the_category(recorder):
    state = gear_turn(SearchSpec(category="gear", keywords=["hat"])).state
    outcomes, state = show_more(state, GEAR)
    assert [p.id for p in outcomes[0].shown] == [3, 4, 5]
    assert outcomes[0].total == 2


def test_the_two_limit_suggestions_keep_a_product_that_misses_the_keyword(recorder):
    catalog = [
        product(1, "Leather Bag", rating=4.9, price=130.0),
        product(2, "Faux Backpack", rating=3.4, price=40.0),
    ]
    spec = SearchSpec(category="gear", keywords=["bag"], price_max=49.99, rating_min=4.5)
    result = run_turn("bag", ConversationState(), catalog, ["gear"], fake_llm_returning(search_parse(spec)))
    assert {p.id for p in result.outcomes[0].shown} == {1, 2}


# --- how many cards ---------------------------------------------------------------


def test_show_all_gives_every_match_a_card_and_leaves_nothing_for_show_more(recorder):
    result = turn("all phones", search_parse(SearchSpec(category="smartphones", show_all=True)))
    outcome = result.outcomes[0]
    assert len(outcome.shown) == outcome.total == 16
    assert not has_more(outcome)


def test_a_refine_keeps_show_all(recorder):
    state = turn("all phones", search_parse(SearchSpec(category="smartphones", show_all=True))).state
    result = turn("cheaper", search_parse(SearchSpec(price_max=500), mode="refine"), state)
    assert result.state.searches[0].show_all is True
    assert len(result.outcomes[0].shown) > CARDS_PER_SEARCH


def test_the_total_counts_all_matches_though_three_cards_show(recorder):
    outcome = turn("phones", search_parse(SearchSpec(category="smartphones"))).outcomes[0]
    assert outcome.total == 16
    assert len(outcome.shown) == 3


def test_show_all_alone_is_not_a_search_of_the_whole_catalog(recorder):
    result = turn("show me everything", search_parse(SearchSpec(show_all=True)))
    assert result.parsed.intent == "needs_clarification"
    assert result.outcomes == []


# --- fallback -----------------------------------------------------------------


def test_loosened_search_keeps_the_original_bound_and_still_shows_cards(recorder):
    result = turn("laptops under $10", search_parse(SearchSpec(category="laptops", price_max=9.99)))

    outcome = result.outcomes[0]
    assert outcome.spec.price_max == 9.99  # the search as asked, before loosening
    assert outcome.loosened == ["price"]
    assert [p.price for p in outcome.shown] == [1099.99, 1399.99, 1499.99]  # nearest to the limit first
    # The stored search is the original too, so a later refine starts from what the user said.
    assert result.state.searches[0].price_max == 9.99


# --- refine -------------------------------------------------------------------


def laptops_state() -> ConversationState:
    """State after 'laptops under $1,500': 3 laptops match (1,099.99, 1,399.99 and 1,499.99)."""
    first = turn("laptops under $1,500", search_parse(SearchSpec(category="laptops", price_max=1500)))
    return first.state


def test_refine_keeps_earlier_fields(recorder):
    state = laptops_state()
    result = turn("cheaper", search_parse(SearchSpec(price_max=1200), mode="refine"), state)

    merged = result.state.searches[0]
    assert merged.category == "laptops"  # kept
    assert merged.price_max == 1200  # overwritten
    assert [p.title for p in result.outcomes[0].shown] == ["Lenovo Yoga 920"]


def test_refine_clear_fields_drops_a_filter(recorder):
    state = laptops_state()
    change = SearchSpec(sort_by="price", clear_fields=["price_max"])
    result = turn("any price is fine", search_parse(change, mode="refine"), state)

    merged = result.state.searches[0]
    assert merged.category == "laptops"
    assert merged.price_max is None
    assert merged.sort_by == "price"


def test_refine_with_out_of_range_index_uses_the_first_search(recorder):
    state = laptops_state()
    result = turn("cheaper", search_parse(SearchSpec(price_max=1200, refines_index=7), mode="refine"), state)
    assert result.state.searches[0].category == "laptops"
    assert result.state.searches[0].price_max == 1200

    result = turn("cheaper", search_parse(SearchSpec(price_max=1200, refines_index=-1), mode="refine"), state)
    assert result.state.searches[0].category == "laptops"


def test_refine_edits_the_search_it_names_and_drops_the_other(recorder):
    first = turn(
        "laptops and sunglasses",
        search_parse(SearchSpec(category="laptops"), SearchSpec(category="sunglasses")),
    )
    result = turn(
        "cheaper sunglasses",
        search_parse(SearchSpec(price_max=25, refines_index=1), mode="refine"),
        first.state,
    )
    assert len(result.state.searches) == 1
    assert result.state.searches[0].category == "sunglasses"
    assert result.state.searches[0].price_max == 25


def test_refine_with_no_previous_search_merges_against_an_empty_one(recorder):
    # The change carries a category, so the merged search is runnable.
    result = turn("sunglasses", search_parse(SearchSpec(category="sunglasses"), mode="refine"))
    assert result.state.searches == [SearchSpec(category="sunglasses")]
    assert len(result.outcomes[0].shown) == 3


def test_refine_that_is_still_empty_gets_the_guard(recorder):
    # No previous search and a change with no field set: nothing to run.
    result = turn("whatever", search_parse(SearchSpec(), mode="refine"))
    assert result.parsed.intent == "needs_clarification"
    assert result.outcomes == []

    # A refine that carries no searches at all.
    result = turn("whatever", ParsedRequest(intent="product_search", mode="refine"))
    assert result.parsed.intent == "needs_clarification"
    assert result.outcomes == []


def test_everything_cleared_refine_gets_the_guard_and_runs_no_search(recorder, monkeypatch):
    state = turn("sunglasses", search_parse(SearchSpec(category="sunglasses"))).state

    def must_not_run(*args, **kwargs):
        raise AssertionError("a search with no field set must never run")

    monkeypatch.setattr(pipeline, "search_with_fallback", must_not_run)

    clear = SearchSpec(clear_fields=["category"])
    result = turn("forget it all", search_parse(clear, mode="refine"), state)

    assert result.parsed.intent == "needs_clarification"
    assert result.outcomes == []
    assert result.state.searches == state.searches  # the old search is kept
    assert result.state.shown == state.shown
    assert recorder.calls[-1][1].intent == "needs_clarification"  # the reply is a clarifying question


# --- show more ----------------------------------------------------------------


def test_show_more_never_repeats_and_keeps_the_searches(recorder):
    state = turn("phones", search_parse(SearchSpec(category="smartphones"))).state
    original_searches = list(state.searches)

    seen = [p.id for p in state.shown]
    for _ in range(10):  # more clicks than there are pages
        outcomes, state = show_more(state, CATALOG)
        new = [p.id for o in outcomes for p in o.shown]
        assert not set(new) & set(seen)  # no repeats
        seen += new
        assert state.searches == original_searches  # never overwritten
        if not new:
            break

    assert sorted(seen) == sorted(p.id for p in CATALOG if p.category == "smartphones")
    assert [p.id for p in state.shown] == seen


def test_show_more_outcome_holds_everything_still_unseen(recorder):
    state = turn("laptops", search_parse(SearchSpec(category="laptops"))).state
    outcomes, new_state = show_more(state, CATALOG)

    assert len(outcomes[0].shown) == 2  # 5 laptops, 3 already shown
    assert len(outcomes[0].products) == 2
    assert not has_more(outcomes[0])  # so main.py shows no button
    assert len(new_state.shown) == 5

    outcomes, _ = show_more(new_state, CATALOG)
    assert outcomes[0].shown == [] and outcomes[0].products == []


def test_show_more_does_not_change_the_state_it_was_given(recorder):
    state = turn("phones", search_parse(SearchSpec(category="smartphones"))).state
    before = state.model_copy(deep=True)
    show_more(state, CATALOG)
    assert state == before


def test_show_more_makes_no_history_change_and_no_llm_call(recorder):
    state = turn("phones", search_parse(SearchSpec(category="smartphones"))).state
    _, new_state = show_more(state, CATALOG)  # takes no llm at all
    assert new_state.history == state.history


def test_show_more_with_no_searches_returns_nothing_and_the_same_state():
    state = ConversationState()
    outcomes, new_state = show_more(state, CATALOG)
    assert outcomes == []
    assert new_state == state


def test_typed_show_more_adds_cards_and_keeps_the_searches(recorder):
    first = turn("phones", search_parse(SearchSpec(category="smartphones")))
    more = turn("show more", ParsedRequest(intent="product_search", mode="show_more"), first.state)

    assert not set(shown_ids(more)) & set(shown_ids(first))
    assert len(shown_ids(more)) == 3
    assert more.state.searches == first.state.searches
    assert len(more.state.shown) == 6  # shown gains the new cards
    assert more.state.history[-2:] == [
        ChatTurn(role="user", text="show more"),
        ChatTurn(role="assistant", text="fake reply"),
    ]


def test_typed_show_more_with_no_previous_search_gets_the_guard(recorder):
    result = turn("show more", ParsedRequest(intent="product_search", mode="show_more"))
    assert result.parsed.intent == "needs_clarification"
    assert result.outcomes == []
    assert result.state.searches == [] and result.state.shown == []


# --- other intents ------------------------------------------------------------


def test_small_talk_keeps_searches_and_shown_cards(recorder):
    first = turn("phones", search_parse(SearchSpec(category="smartphones")))
    result = turn("thanks!", ParsedRequest(intent="small_talk"), first.state)

    assert result.outcomes == []
    assert result.state.searches == first.state.searches
    assert result.state.shown == first.state.shown
    assert len(result.state.history) == 4

    # A follow-up after the small talk still refines the earlier search.
    after = turn("cheaper", search_parse(SearchSpec(price_max=300), mode="refine"), result.state)
    assert after.state.searches[0].category == "smartphones"
    assert after.state.searches[0].price_max == 300


def test_off_catalog_shows_no_cards(recorder):
    parsed = ParsedRequest(intent="off_catalog", unsupported=["a flight to Tokyo"])
    result = turn("a flight to Tokyo", parsed)
    assert result.outcomes == []
    assert result.state.shown == []
    assert recorder.calls[0][2] == []  # the reply writer got no products


def test_needs_clarification_shows_no_cards(recorder):
    result = turn("something cool", ParsedRequest(intent="needs_clarification"))
    assert result.outcomes == []


def test_a_mixed_request_still_shows_cards_and_passes_the_unsupported_part(recorder):
    parsed = ParsedRequest(
        intent="product_search",
        mode="new",
        searches=[SearchSpec(category="sunglasses")],
        unsupported=["book a flight"],
    )
    result = turn("book a flight and find sunglasses", parsed)
    assert len(result.outcomes[0].shown) == 3
    assert recorder.calls[0][1].unsupported == ["book a flight"]


# --- language -----------------------------------------------------------------


def test_reply_writer_gets_the_wordful_message_when_the_user_answers_with_a_number(recorder):
    history = [
        ChatTurn(role="user", text="אני מחפש בושם"),
        ChatTurn(role="assistant", text="מה התקציב שלך בדולרים?"),
    ]
    state = ConversationState(history=history)
    turn("$300", ParsedRequest(intent="needs_clarification"), state)
    assert recorder.calls[0][0] == "אני מחפש בושם"


def test_the_message_itself_wins_when_it_has_a_letter(recorder):
    state = ConversationState(history=[ChatTurn(role="user", text="אני מחפש בושם")])
    turn("under $300 please", ParsedRequest(intent="needs_clarification"), state)
    assert recorder.calls[0][0] == "under $300 please"


def test_a_message_in_another_script_counts_as_words(recorder):
    state = ConversationState(history=[ChatTurn(role="user", text="hello")])
    turn("שלום", ParsedRequest(intent="small_talk"), state)
    assert recorder.calls[0][0] == "שלום"


def test_with_no_letters_anywhere_the_message_itself_is_passed(recorder):
    state = ConversationState(history=[ChatTurn(role="user", text="123")])
    turn("$300", ParsedRequest(intent="needs_clarification"), state)
    assert recorder.calls[0][0] == "$300"


def test_assistant_text_is_not_used_as_the_users_words(recorder):
    state = ConversationState(history=[ChatTurn(role="assistant", text="What is your budget?")])
    turn("$300", ParsedRequest(intent="needs_clarification"), state)
    assert recorder.calls[0][0] == "$300"


# --- errors and state ---------------------------------------------------------


def test_llm_exception_propagates_and_the_passed_state_is_unchanged(recorder):
    state = turn("phones", search_parse(SearchSpec(category="smartphones"))).state
    before = state.model_copy(deep=True)

    def broken_llm(messages, response_model=None):
        raise TimeoutError("model timed out")

    with pytest.raises(TimeoutError):
        run_turn("cheaper", state, CATALOG, CATEGORIES, broken_llm)
    assert state == before


def test_reply_writer_exception_propagates_too(monkeypatch):
    def broken_write_reply(message, parsed, outcomes, llm):
        raise TimeoutError("model timed out")

    monkeypatch.setattr(pipeline, "write_reply", broken_write_reply)
    state = ConversationState()
    with pytest.raises(TimeoutError):
        turn("laptops", search_parse(SearchSpec(category="laptops")), state)
    assert state == ConversationState()


def test_run_turn_never_changes_the_state_it_was_given(recorder):
    state = turn("phones", search_parse(SearchSpec(category="smartphones"))).state
    before = state.model_copy(deep=True)

    turn("cheaper", search_parse(SearchSpec(price_max=300), mode="refine"), state)
    turn("new thing", search_parse(SearchSpec(category="laptops")), state)
    turn("show more", ParsedRequest(intent="product_search", mode="show_more"), state)
    turn("hi", ParsedRequest(intent="small_talk"), state)
    assert state == before


def test_invalid_parser_output_becomes_a_clarifying_turn(recorder):
    def garbage_llm(messages, response_model=None):
        return "not json"

    result = run_turn("phones", ConversationState(), CATALOG, CATEGORIES, garbage_llm)
    assert result.parsed.intent == "needs_clarification"
    assert result.outcomes == []


# --- card props ---------------------------------------------------------------


def test_card_props_have_the_shape_the_card_element_reads(recorder):
    result = turn("laptops", search_parse(SearchSpec(category="laptops")))
    props = card_props(result.outcomes[0])

    assert list(props) == ["products"]
    assert len(props["products"]) == 3
    for card in props["products"]:
        assert set(card) == {"id", "title", "description", "price", "rating", "brand", "thumbnail", "category"}
    assert props["products"][0]["title"] == result.outcomes[0].shown[0].title
    # Props travel to the browser as JSON, so they must serialize.
    json.dumps(props)


def test_card_props_follow_shown_not_products(recorder):
    result = turn("phones", search_parse(SearchSpec(category="smartphones")))
    assert len(result.outcomes[0].products) == 16
    assert len(card_props(result.outcomes[0])["products"]) == 3


def test_has_more_is_true_only_while_matches_remain_without_a_card(recorder):
    result = turn("laptops", search_parse(SearchSpec(category="laptops")))
    assert has_more(result.outcomes[0])  # 5 laptops, 3 shown

    result = turn("sunglasses", search_parse(SearchSpec(category="sunglasses", top_k=5)))
    assert not has_more(result.outcomes[0])  # all 5 shown
