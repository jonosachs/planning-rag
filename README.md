# Planning-RAG 🏡

A retrieval-augmented generation app that answers Victorian planning questions from
the **ordinance text**, retrieved live from the Victorian planning API, with every
answer tied back to the clauses it came from.

---

## Pipeline

```text
Index: load  →  chunk  →  embed  →  vector store
Query: embed query  →  retrieve (vector similarity)  →  prompt (query + context)  →  cited answer
```

Source API: `https://api.app.planning.vic.gov.au/planning/v2/schemes/`

A scheme payload nests clause references several levels deep
(`scheme → clauses → subClauses → sections → schedules`). `flatten_clause_ref_nodes`
recursively flattens that tree, carrying the overarching clause title down to its
children as a `section` tag. The refs are optionally filtered by keyword and capped,
then each clause document is fetched individually and its HTML content converted to
text.

---

## Architecture

```text
src/
├── main.py              # entry points: run_indexing / run_query
├── planning/            # DataSource: fetch scheme → flatten clause tree → HTML→text → chunk
├── indexing/            # DataSource / Embedder / VectorStore interfaces + Gemini + ChromaDB impls
├── llm/                 # Llm ABC + Prompt, and a Gemini wrapper with a Pydantic response schema
└── query/               # prompt assembly, citation parsing/grouping, CLI rendering
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

```text
Index: ClauseRef → ClauseDoc → Chunk (+ ClauseMetaData) → EmbeddedChunk
Query: PlanningCitation → Prompt → LlmPlanningResponse → citations grouped by section
```

`ClauseRef` (id, title, section, enough to fetch) → `ClauseDoc` (full clause with
content and gazettal metadata) → `Chunk` (~750 chars, split on paragraph boundaries and
allowed to overshoot rather than break one, carrying `ClauseMetaData`). `ClauseDoc` and
`ClauseMetaData` share a `ClauseFields` base, so metadata is a dump of the clause minus
its content, plus `chunk_index`. Optional fields default to `""` because ChromaDB
cannot store `None`. Each chunk's text is prefixed with its section and parent title so
the embedding keeps that context.

Retrieved chunks become `PlanningCitation` objects with a 0-based `citation_index`, and
the context block labels each one with that index. Answers come back as a
`LlmPlanningResponse` — a Pydantic schema passed to Gemini as a structured-output spec —
where `citation_idxs` points back at the indexes used, so citations are matched by index
rather than scraped out of prose. The CLI groups the selected citations by section. The
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

`.gitignore` excludes `assets/`, `tests/`, `admin/`, `chroma_db/`, `tmp/` and the tool
caches, so a fresh clone has no index and has to be indexed before it can be queried.

---

## Running it

On the first run you need to index the planning data first with the argument `index`.
The defaults live in `src/main.py` (`PLANNING_SCHEME = "Port Phillip"`,
`MAX_RESULTS = None`, `KEY_WORD = None`) and each can be overridden per run:

```sh
.venv/bin/python -m src.main index
.venv/bin/python -m src.main index --scheme "Port Phillip" --key-word heritage --max-results 100
```

Then run the main routine:

```sh
.venv/bin/python -m src.main
```

---

## Current state

Project is a work in progress. Currently experimenting with ingesting architectural drawings to cross-reference against planning requirements on branch `experimental/geometry-grounded-extraction`

### Known issues

- Chunk ids are `scheme_id:ordinance_id:chunk_index` and upserted, so re-indexing
  overwrites in place — but if a clause chunks into fewer pieces than last run, the
  leftover high-index chunks stay in the collection.
- `tests/` is git-ignored, so there is no runnable suite.

### Debugging

`ruff check src tests`        # lint: unused imports, dead code, bug-prone patterns
`ruff format src tests`       # formatting (Black-compatible)
`pyright src`                 # type checking

