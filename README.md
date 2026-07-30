# Planning-RAG 🏡

A retrieval-augmented generation app that answers Victorian planning questions from
the **ordinance text**, retrieved live from the Victorian planning API, with every
answer tied back to the clauses it came from.

A second data source reads **architectural drawings** (PDF text features) into the
same index, so drawings and controls can eventually be queried together.

> **Status:** the planning path works end to end. The drawings source loads but has
> no chunker of its own yet. See [Current state](#current-state).

---

## Pipeline

```text
Index:  load  →  chunk  →  embed  →  ChromaDB
Query:  embed query  →  retrieve (vector similarity)  →  prompt (query + context)  →  cited answer
```

Source API: `https://api.app.planning.vic.gov.au/planning/v2/schemes/`

A scheme payload nests clause references several levels deep
(`scheme → clauses → subClauses → sections → schedules`). `flatten_clause_nodes`
flattens that tree, the refs are optionally filtered by keyword and capped, then each
clause document is fetched individually and its HTML content converted to text.

---

## Architecture

```text
src/
├── main.py              # entry points: run_indexing / run_query
├── planning/            # DataSource: fetch scheme → flatten clause tree → HTML→text → chunk
├── drawings/            # DataSource: PDF pages → planning-relevant pages → render → text features → chunk
├── indexing/            # DataSource / Embedder / VectorStore interfaces + Gemini + ChromaDB impls
├── llm/                 # Gemini wrapper with a Pydantic response schema
└── query/               # prompt assembly, CLI, citation rendering
```

The design point is `src/indexing/interfaces.py`, which defines three ABCs:

| ABC | Contract |
| --- | --- |
| `DataSource` | `load()` → raw items, `chunk(items)` → `list[Chunk]` |
| `Embedder` | `embed_chunks(chunks)`, `embed_text(text)` |
| `VectorStore` | `write(chunks)`, `run_query(vector)`, `get_all()` |

`run_indexing_pipeline(source, embedder, store)` depends only on those three, so
planning text and drawings share one indexing path and the Gemini/Chroma choices are
swappable without touching either source. Adding a third source means implementing
`DataSource` and nothing else.

### Data model

`ClauseRef` (id + title, enough to fetch) → `ClauseDoc` (full clause with content and
gazettal metadata) → `Chunk` (≤750 chars, split on paragraph boundaries, carrying
`ClauseMetaData`). The metadata is what surfaces as citations, so chunking preserves
`ordinance_id`, `title` and `chunk_index` per chunk.

Answers come back as a `LlmPlanningResponse` — a Pydantic schema passed to Gemini as a
structured-output spec, so citations are parsed rather than scraped out of prose. The
system prompt constrains the model to the retrieved context and tells it to distinguish
site-specific controls from general requirements.

---

## Requirements

- Python 3.13+ (`pyproject.toml` declares `>=3.14`; see [Current state](#current-state))
- A Google Gemini API key

```sh
python -m venv .venv
.venv/bin/pip install -r requirements.txt
echo 'GEMINI_API_KEY=...' > .env
```

| Purpose | Model |
| --- | --- |
| Embeddings | `gemini-embedding-001` |
| Response generation | `gemini-3-flash-preview` |

`.gitignore` excludes `assets/`, `tests/`, `admin/`, `chroma_db/` and `tmp/`, so a
fresh clone has no drawings and no index. The drawings source expects
`assets/plans.pdf`, and renders page images into `tmp/`, which it creates on demand.

---

## Running it

There is one entry point; `run_query` seeds the index before every query.

```sh
.venv/bin/python -m src.main
```

Scheme (`Port Phillip`) and the drawings path are hardcoded in `src/main.py`.

---

## Current state

The `refactor: reorganize rag pipeline modules` commit renamed `src/rag/` to
`src/indexing/` and split the planning pipeline, leaving dangling references that made
`src.main` unimportable. Those have been repaired: fetch → clean → chunk → write now
runs, verified against the live API (12 overshadowing clauses → 20 chunks) and against
a throwaway Chroma collection.

### Known issues

- **The drawings source cannot chunk.** `src/drawings/chunk.py` is a copy of the
  planning chunker — it imports `ClauseDoc` and reads `clause.content`, but
  `DrawingsSource` feeds it `PageFeautres`, so `batch_chunk` raises `AttributeError`.
  Drawings need a chunker of their own; what constitutes a chunk of a drawing page,
  and what metadata it should carry, is still an open design question.
- `run_indexing` writes planning **and** drawings into the same `planning` collection,
  so drawing chunks would be retrieved as answers to clause questions.
- `run_query` calls `run_indexing()` on every invocation, re-fetching and re-embedding
  the whole scheme before answering.
- Chunk ids are random UUIDs, so re-indexing duplicates every chunk rather than
  upserting over the previous run.
- `src/llm/interace.py` is an empty file and a typo for `interface.py` — the `Llm` ABC
  that would match the other subsystems' interface pattern was never written.
- `src/drawings/schemas.py` exports `PageFeautres` (typo for `PageFeatures`).
- `PlanningSource` hardcodes `max_results=100`.
- `requirements.txt` and `pyproject.toml` list dependencies separately and can drift.
- `[tool.pytest.ini_options]` is configured but `pytest` is in neither dependency list,
  and `tests/` is git-ignored, so there is no runnable suite.
- `pyproject.toml` requires Python `>=3.14`; the working `.venv` is 3.13.14.