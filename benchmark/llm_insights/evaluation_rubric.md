# Evaluation Rubric — Live Local-LLM Benchmark (STEP 5)

## Grounding metrics (deterministic, automatic)

All grounding metrics are computed by the runner using the production
`GroundingValidator`; no LLM judges its own output here.

| Metric | Definition |
|--------|-----------|
| VALID_JSON_RATE | % of raw LLM responses that parse to a JSON object **and** pass Pydantic `LLMInsightOutput` schema validation. |
| GROUNDING_PASS_RATE | % of parsed responses accepted by `GroundingValidator` (fact IDs + numbers + no forbidden/causality claims). |
| UNSUPPORTED_NUMERIC_RATE | % of generations rejected because of a numeric literal absent from the verified payload. |
| UNKNOWN_FACT_REFERENCE_RATE | % of generations referencing a fact ID not present in the payload. |
| FORBIDDEN_CLAIM_RATE | % with fraud/compliance (or equivalently causality) overclaim wording. |
| RECOMMENDATION_GROUNDING_RATE | % of LLM recommendations whose text matches one of the permitted `recommendation_candidates` (or empty when none exist). |

## Quality / synthesis metrics

Scored deterministically where possible, manually via this rubric otherwise.

| Dimension | Deterministic proxy |
|-----------|--------------------|
| FACT_COVERAGE | high-priority expected facts referenced by generated fact IDs |
| FACT_PRECISION | grounded claims / total claims (from grounding gate) |
| RELEVANCE | output answers the analytical question (question-token overlap heuristic) |
| REDUNDANCY | output adds synthesis, not a verbatim restatement of numbers (length/token heuristic + manual) |
| RECOMMENDATION_USEFULNESS | prioritizes the supplied recommendation candidates |
| LIMITATION_AWARENESS | mentions evidence limitations when the fixture declares some |

## Value-added score (manual, 0–2 per dimension)

Rated against the **deterministic formatter** as baseline per case.

| Score | Meaning |
|-------|---------|
| 0 | worse / no added value over deterministic formatter |
| 1 | modest improvement |
| 2 | clearly better |

Dimensions (factual correctness excluded — grounding is a separate hard gate):

- synthesis
- prioritization
- readability
- question relevance
- recommendation phrasing

## Language quality (manual; French and English rated separately)

1 = poor, 5 = excellent per axis.

- grammatical correctness
- natural business language
- banking terminology accuracy
- clarity
- unnecessary anglicisms (French)
- robotic wording
