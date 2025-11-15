# Agent Prompts (Internal)

These prompts are used by the agents. They are defined in `src/llm/prompt_templates.py`.

## Query Understanding Agent

- **Role**: Parse user intent and extract books, editions, sections, and operation types.
- **Output**: JSON with `intent_type`, `entities`, `operations`, `confidence`. Low confidence triggers an ambiguity note.

## Retrieval Planning Agent

- **Role**: Given the parsed intent, choose strategy (section_exact, section_semantic, multi_edition, cross_book) and list tool steps with parameters.
- **Output**: JSON with `strategy`, `steps` (tool name + parameters + reasoning), `expected_sections`, `fallback_strategy`.

## Section Matching Agent

- **Role**: When no precomputed alignment exists, decide if two sections (from two editions) are the same logical section using location, title, preview, and similarity scores.
- **Output**: JSON with `same_section`, `confidence`, `reasoning`.

## Comparison Agent

- **Role**: Compare two (or more) section texts along content changes, clarity, depth, tone. Must quote and cite.
- **Output**: JSON with `summary`, `dimensions`, `citations`, `sections_compared`.

## Summarization Agent

- **Role**: Summarize a single section or summarize differences between editions. Concise, factual, with citations.
- **Output**: JSON with `content`, `citations`, `confidence`, `summary_type`.

## Verification Agent

- **Role**: Check that the final response is grounded in the provided source context; flag unsupported claims and citation errors.
- **Output**: JSON with `is_grounded`, `unsupported_claims`, `citation_errors`.

All agents use Ollama (local) with low temperature (0.1–0.2) and, where applicable, `format="json"` for structured output.
