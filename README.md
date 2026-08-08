# Planning-RAG 🏡

A retrieval-augmented generation app that answers Victorian planning questions from
the **ordinance text**, retrieved live from the Victorian planning API, with every
answer tied back to the clauses it came from.

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

`run_indexing_pipeline(source, embedder, store)` abstracts these three components, so
indexing tools are flexible. 

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

- Python 3.13+ 
- A Google Gemini API key

```sh
python -m venv .venv
.venv/bin/pip install . 
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

On the first run you need to index the planning data first with the argument `index`. Set global vars for max results and key words in main.py. Defaults to max_results=100, key_words = None.

```sh
.venv/bin/python -m src.main index
```

Then run the main routine:

```sh
.venv/bin/python -m src.main
```

---

## Current state

Project is a work in progress. Currently experimenting with ingesting architectural drawings to cross-reference against planning requirements on branch `experimental/geometry-grounded-extraction`

### Known issues

- Chunk ids are random UUIDs, so re-indexing duplicates every chunk rather than
  upserting over the previous run.
- `tests/` is git-ignored, so there is no runnable suite.

### Debugging

`ruff check src tests`        # lint: unused imports, dead code, bug-prone patterns
`ruff format src tests`       # formatting (Black-compatible)
`pyright src`                 # type checking

