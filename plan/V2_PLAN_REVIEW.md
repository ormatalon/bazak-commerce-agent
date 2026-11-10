# Critique of the first V2 plan

Reviewed and revised: 9 November 2026. Companion implementation plan: [V2_PLAN.md](V2_PLAN.md).

The first plan covered the requested engineering, datasets, scoring, and LangSmith work, but it was not ready to execute as written. It contained a potentially misleading relevance gate, an unreachable metric target for broad queries, and several unspecified product behaviors. The revision fixes the evaluation definitions and execution order, and makes unresolved design changes visible.

## Most important findings

### 1. High — z-scores cannot establish that a requested product exists

The plan treated relative catalog similarity as sufficient evidence of product-type relevance. An unsupported request still has a best match. In particular, shifting or scaling every product's similarity by the same positive factor leaves its z-scores unchanged; absolute match quality has disappeared.

**Revision:** added a Phase 2 feasibility checkpoint using unsupported types, close wrong-type negatives, and catalog-composition changes. Require measured false acceptance and false abstention. An absolute floor or compatibility check is a possible design amendment if needed, not a silently added production rule. No-match wording must reflect uncertainty.

**Remaining decision:** whether the design's z-score gate passes those tests, and what additional check is acceptable if it fails. This cannot be settled by editing a plan alone.

### 2. High — the Recall@10 release target could be impossible

If a query has 20 relevant products, perfect top-10 retrieval still gives ordinary Recall@10 of 50%. The original >=90% target would penalize correct broad searches. Judging only the returned candidate pool would also hide relevant products outside the pool.

**Revision:** report ordinary recall with its ceiling, achievable Recall@10, and Hit@10. Reserve true recall/nDCG for queries with complete catalog judgments; use judged precision and annotation coverage for pooled labels. Separate semantic relevance, numeric eligibility, and fallback status.

### 3. High — top-10 truncation changed “cheapest” and could exhaust show-more

Sorting only the ten most similar products may omit a cheaper relevant item. Excluding shown IDs after truncation can report exhaustion even when more relevant inventory exists.

**Revision:** propose relevance checking and requested sorting over all eligible inventory, with pagination over the full list. Add tests with more than ten relevant products. Retaining candidate-only sorting is still a documented option, but its claim and pagination must be explicit.

**Remaining decision:** approve the all-qualified sorting interpretation in the design, or retain the narrower candidate-only meaning. The revised plan identifies this as a design change rather than presenting it as already agreed.

### 4. High — labels arrived too late and “held-out” overstated independence

Thresholds cannot be calibrated before reviewed relevance labels exist. The existing cases have already influenced V1 fixes and have been read during planning; splitting them now does not make them an untouched benchmark.

**Revision:** move initial labeling and split manifests into Phase 1. Use existing data for regression, keep paraphrases together, and add new reviewer-authored prospective test queries. Identify who drafts and reviews labels. Treat annotation as real project work.

### 5. Medium — search structure and fallback state were underspecified

Alternative gift directions are different from two independent requests with different budgets. Comparing raw similarity across different directions is unjustified. Fallback could also overwrite a user's saved budget or loosen an unrelated rating constraint.

**Revision:** distinguish requests from directions, merge directions by deterministic round-robin, preserve original constraints in conversation state, and record only relaxations actually used. Specify partial-result filling, show-more alternatives, two-sided price ranges, and strict currency-bound arithmetic.

**Remaining decision:** review the proposed two-sided-range fallback ordering against labeled examples before implementation.

### 6. Medium — monitoring scope was larger than the local application needs

Automatic synchronization, online judges, scheduled alerts, and multiple statistical thresholds were mixed into the core delivery. The time estimate did not account for annotation, uncertain code reuse, or SDK/environment setup.

**Revision:** require traces, versioned experiment snapshots, shared evaluators, monitoring views, and a runbook. Defer automated sync, judges, and alerts. Remove the unsupported duration estimate and establish a small end-to-end milestone first. Include slow-exporter isolation and trace flushing.

### 7. Medium — safety percentages sounded stronger than their evidence

A 100% score over a small suite does not prove general safety. Code checking a structured exclusion field cannot detect an exclusion that the parser omitted; structured disclosure metadata does not establish that the user saw the explanation.

**Revision:** distinguish detected rule compliance from reviewed semantic correctness, retain unknowns, publish counts and annotation coverage, and report every critical regression. Describe zero failures as an observed test result. Keep a judge as secondary evidence only.

## Assessment after revision

The plan now has an executable order, a smaller required scope, and scoring definitions that match the evidence available. It is ready for the foundation and feasibility work. It is not evidence that V2 works: model viability, abstention accuracy, label coverage, quality targets, and local performance still need measurement.

No application code, labels, experiments, or LangSmith account configuration were changed during this review. The original Design V2 document remains unchanged; proposed amendments are identified in the plan for a deliberate implementation decision.
