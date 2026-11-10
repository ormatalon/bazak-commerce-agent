# Bazak Shopping Copilot V2

A local shopping assistant over the DummyJSON catalog. Chat in English or Hebrew, see product cards, and return to saved conversations.

## Versions

- **`v1`:** the original filter-and-keyword approach, copied from `staging` at commit `18af131`. Use that branch's README for V1 setup; it does not need the embedding model.
- **`v2`:** semantic ranking and product-type checking.
- **`master`:** the current V2 application, including subsequent fixes. This README describes `master`.
- **Comparison:** see [V1 versus V2](#v1-versus-v2) for the approach and the [experience evaluation](evals/EXPERIENCE_PILOT_RESULTS.md) for actual replies and results.

## Setup

Use branch `master`, Python 3.12 and [uv](https://docs.astral.sh/uv/getting-started/installation/). Run commands from the repository root.

### 1. Install dependencies

**Windows — PowerShell**

```powershell
uv python install 3.12
uv venv --python 3.12 .venv
uv pip install --python .venv/Scripts/python.exe -r requirements.txt --index https://download.pytorch.org/whl/cpu --index https://pypi.org/simple --index-strategy unsafe-best-match
if (!(Test-Path .env)) { Copy-Item .env.example .env }
.venv/Scripts/python.exe -m chainlit create-secret
```

**macOS — Apple Silicon, macOS 14+**

```bash
uv python install 3.12
uv venv --python 3.12 .venv
uv pip install --python .venv/bin/python -r requirements.txt --index-url https://pypi.org/simple --only-binary torch,numpy
if [ ! -e .env ]; then cp .env.example .env; fi
.venv/bin/python -m chainlit create-secret
```

Create a separate environment on each machine. Intel Macs are not supported by the pinned PyTorch version. Mac dependencies were resolved, but the app has not been tested on a physical Mac. See [detailed setup and troubleshooting](plan/SETUP.md).

### 2. Configure `.env`

- `OPENAI_API_KEY`: your model API key.
- `APP_USERNAME` and `APP_PASSWORD`: choose a local login.
- `CHAINLIT_AUTH_SECRET`: copy the generated secret, or keep your existing one.

`.env` is ignored by Git. LangSmith tracing is optional; see [monitoring setup](plan/MONITORING.md).

### 3. Start the app

**Windows**

```powershell
.venv/Scripts/python.exe -m app.embeddings --download
.venv/Scripts/python.exe -m chainlit run app/main.py
```

**macOS**

```bash
.venv/bin/python -m app.embeddings --download
.venv/bin/python -m chainlit run app/main.py
```

Open **http://localhost:8000** and sign in. On later runs, only the last command is needed. Model calls require internet access; the embedding model runs locally on CPU.

## Architecture

### UI framework

1. **Streamlit:** quick for a demo, but its rerun model adds work to coordinate chat state and saved conversations.
2. **Chainlit:** provides chat, a conversation sidebar and resume hooks; custom elements support product cards.
3. **Custom React + Python API:** more UI control, but requires building the chat connection, history sidebar and resume flow.

I chose **Chainlit** to spend less time building chat features and more time on retrieval and evaluation.

### Pipeline framework

1. **Plain Python:** explicit steps and typed data make the flow easy to trace and test.
2. **LangChain:** could organize model calls and retrieval, but would add another abstraction without removing much code here.
3. **LangGraph:** useful for branching and resumable workflows; this mostly fixed sequence does not need a graph.

I chose **plain Python** because the flow is small. Chainlit and SQLite handle conversation persistence.

### Message flow

1. `gpt-6-luna` parses intent, constraints and follow-ups.
2. Local multilingual E5 embeddings rank products.
3. `gpt-6-luna` checks shortlisted product types; Python applies filters and selects cards.
4. `gpt-6-luna` writes a reply using the selected products. Chainlit renders cards and saves state.

## Retrieval

### Catalog access

- `GET /products?limit=0` fetches all products from `https://dummyjson.com`.
- `GET /products/category-list` supplies valid category names.
- A local cache avoids repeated API calls and keeps one consistent catalog during a chat.
- Local search gives control over filtering, ranking and pagination. The tradeoff is stale data: the cache is not automatically refreshed.

### V1 versus V2

1. **V1 (`v1`):** extracts filters and keywords, then searches locally. Answers are focused, but vague requests can lead to clarification or no useful results.
2. **V2 (`v2`):** adds semantic ranking and several possible directions for vague requests. It offers broader suggestions, but evaluations do not establish an overall improvement over V1.

V2 can interpret the same request differently across runs because parsing and product-type checks use a model. The local ranking is deterministic for the same parsed request and index. In manual use, "all sunglasses" has returned four or five products, and "glasses" has included a drinking glass. These observations show variability and ambiguity; they are not a measured failure rate.

### Request handling

- **Vague:** suggest up to three directions for requests such as "something nice for my wife", then ask a follow-up.
- **Off-catalog:** decline unrelated requests such as "a flight to Tokyo" without cards. Unsupported product types may return a no-match explanation.
- **Multi-intent:** search each request separately, preserving its budget and constraints.
- **Follow-ups:** use recent messages, saved searches and shown products. "Show more" skips previously shown products.
- **Alternatives:** fill empty slots with disclosed price/rating exceptions. Explicit strict-limit or "no alternatives" requests disable this fallback, including after resume and follow-ups. Users can allow alternatives again. Exclusions are never relaxed.
- **Currency:** convert budgets using Frankfurter reference rates, save the quote for the conversation and disclose its source/date. During an outage, use a recent cached quote or ask for a USD budget.

## Conversations and storage

- **Storage:** local `chat.db`, using SQLite through Chainlit's SQLAlchemy data layer. SQLite needs no separate database server for this single-user app.
- **Resume:** save history, search constraints and card data so previous chats can continue after refresh.
- **Full disk or failed write:** warn that the message may not be saved; the chat can continue.
- **Corruption at startup:** keep a backup and create a fresh database. Old chats are no longer visible in the app.
- **Database deleted during chat:** recreate it and save future messages. Deleted history is not restored.

## Tests and evaluation

- **92 offline tests:** cover filters, exclusions, sorting, pagination, strict limits, alternatives, currency, state restoration, storage and selected UI callbacks.
- **167 source cases:** cover explicit searches, behavior, adversarial requests and Hebrew.
- **Full suite before the strict-limit fix:** all 167 cases completed without execution errors; extraction exact match was 71/72. See [results and remaining issues](plan/LATEST_EVALUATION.md).
- **20-case experience pilot:** compares V1/V2 recommendations, courtesy and follow-up progress.
- **Version differences:** some source labels expect V1's clarification or fallback behavior. Keep those compatibility scores separate from V2 usefulness. Deterministic F1 uses all exact matches before the card limit, excluding alternatives, so filling three cards does not by itself explain a lower F1.
- **Regressions caught:** dropped budgets, repeated cards, incorrect state updates and replies sent to the wrong conversation.
- **Blind spots:** offline tests use fake model replies and vectors. Neither the tests nor recorded evaluations verify actual browser rendering or refresh. Semantic judgments are not independent human ratings.

Run offline tests on Windows:

```powershell
$testTemp = Join-Path (Get-Location) ('.test-tmp/' + [guid]::NewGuid().ToString('N'))
.venv/Scripts/python.exe -m pytest tests -q -p no:cacheprovider --basetemp $testTemp
```

On macOS, run `.venv/bin/python -m pytest tests -q`.

For a live evaluation, run `.venv/Scripts/python.exe -m evals.run_evals --live` (use `.venv/bin/python` on macOS). This makes paid model calls and uses frozen currency rates by default.

## Known limitations

- Ranking can omit valid products; relevance thresholds are still provisional.
- Permitted alternatives can still make answers noisy or be too far from the requested budget.
- Some recorded follow-ups lose available context.
- The catalog cache can become stale; local retrieval would need revisiting for a much larger catalog.
- The latest full evaluation is one model run; it does not establish consistency across repeated requests or overall superiority to V1.

## With another week

1. **Measure the shopping experience better.** In manual use, V2 often feels more helpful on vague requests, but the current numbers do not clearly capture that. I would expand the experience dataset with independently written gift, discovery and follow-up requests, alongside explicit searches and genuine no-match cases. Compare V1/V2 without showing reviewers the version names, scoring relevance, usefulness, unnecessary refusals and constraint compliance. Keep unseen cases separate from tuning to test whether V2's apparent strengths hold up, including where it loses to V1.
2. **Reduce inconsistent decisions.** Repeat identical requests with the same catalog and conversation state, then compare parser output, relevance scores and product-type decisions to locate the variation. Add clear rules and regression cases for price boundaries, singular/plural counts and ambiguous types such as drinking glasses versus eyewear. Use context or a clarification when needed. The goal is consistent interpretation and product selection; reply wording can still vary.
3. **Improve permitted alternatives.** With strict-limit opt-out implemented, measure when alternatives help and when they just pad the answer. Review their relevance and distance from the requested budget, then tune selection using those judgments.
4. **Test the actual browser flow.** Add automated checks for product cards, refresh, new conversations and resuming old chats, plus visible storage-failure notices. These cover behavior the Python tests cannot verify.

## Further reading

- [Latest master evaluation](plan/LATEST_EVALUATION.md)
- [Final evaluation and remaining gaps](plan/FINAL_EVALUATION.md)
- [V1/V2 experience comparison](evals/EXPERIENCE_PILOT_RESULTS.md)
- [Implementation decisions](DECISIONS.md)
- [Implementation plan](plan/V2_PLAN.md)
- [Monitoring and detailed evaluation commands](plan/MONITORING.md)
