# Planning-RAG 🏡

Answers Victorian planning questions from two sources of truth: the **ordinance text**
(retrieved from the Victorian planning API) and the **architectural drawings** for a
proposed development (measured out of the PDF's vector geometry).

Two subsystems:

| Subsystem | Location | Status |
| --- | --- | --- |
| RAG over planning scheme clauses | `src/` | working |
| Geometry-grounded drawing extraction & compliance triage | `spikes/geometry_extraction/` | spike |

The design premise is that an LLM should **not** be asked to read a setback or a
height off a drawing. Code extracts deterministic geometry; the model is used only
for localisation and semantic identification ("which edge is the street frontage?"),
never for measurement.

---

## Requirements

- Python 3.13+ (`pyproject.toml` currently declares `>=3.14`; see [Known rough edges](#known-rough-edges))
- A Google Gemini API key in `.env` as `GEMINI_API_KEY`
- Drawing PDFs in `assets/` (git-ignored — see [Assets](#assets))

```sh
python -m venv .venv
.venv/bin/pip install -r requirements.txt
echo 'GEMINI_API_KEY=...' > .env
```

Models used:

| Purpose | Model |
| --- | --- |
| Embeddings | `gemini-embedding-001` |
| Text + vision generation | `gemini-3-flash-preview` |
| Envelope colouring (region hint only) | `gemini-2.5-flash-image` |

---

## Part 1 — Planning scheme RAG (`src/`)

### Pipeline

```text
Ingest  →  clean  →  chunk  →  embed  →  ChromaDB
Query   →  embed  →  retrieve (vector similarity)  →  prompt (query + context)  →  cited answer
```

Source: `https://api.app.planning.vic.gov.au/planning/v4/schemes/{schemeID}`
(see `admin/PLANNING_API.md`).

### Layout

```text
src/
├── main.py              # entry points: run_planning_indexing / run_drawing_indexing / run_query
├── planning/            # DataSource: fetch scheme → flatten clause tree → HTML→text → chunk
├── drawings/            # DataSource: PDF pages → planning-relevant pages → render → text features → chunk
├── indexing/            # DataSource / Embedder / VectorStore interfaces + Gemini + ChromaDB impls
├── llm/                 # Gemini wrapper with a Pydantic response schema
└── query/               # prompt assembly, CLI, citation rendering
```

`src/indexing/interfaces.py` defines three ABCs (`DataSource`, `Embedder`,
`VectorStore`); `run_indexing_pipeline` depends only on those, so planning text and
drawings share one indexing path and the Gemini/Chroma choices are swappable.

### Running it

There is no `__main__` block wired up yet (it is commented out in `src/main.py`), so
call the entry points directly:

```sh
# Seed the planning collection (Port Phillip, keyword-filtered, 50 clauses max)
.venv/bin/python -c "from src.main import run_planning_indexing; run_planning_indexing()"

# Seed the drawings collection from assets/plans.pdf
.venv/bin/python -c "from src.main import run_drawing_indexing; run_drawing_indexing()"

# Ask a question
.venv/bin/python -c "from src.main import run_query; run_query()"
```

Scheme, keyword filter and clause cap are constants at the top of `src/main.py`.

---

## Part 2 — Geometry-grounded extraction (`spikes/geometry_extraction/`)

Reads measurable facts (setbacks, building height, site coverage) off a drawing set,
then compares them to the retrieved planning controls.

### Entry point

`run_auto.py` classifies the query and dispatches to one of three paths:

```sh
.venv/bin/python -m spikes.geometry_extraction.run_auto "do the setbacks comply"
.venv/bin/python -m spikes.geometry_extraction.run_auto "what is the site coverage and does it comply"
.venv/bin/python -m spikes.geometry_extraction.run_auto "does this renovation comply"
```

| Route | Handler | Used for |
| --- | --- | --- |
| `geometric` | `compliance.assess_setback_compliance` | per-boundary setbacks and height — values must be measured |
| `stated` | `read_answer.assess_query` | values printed in a data block (site coverage, POS, permeability) |
| `overall` | `triage.triage_project` | "does the whole thing comply?" — runs the checklist and aggregates |

Requires the `planning` collection to be seeded first (Part 1), because every path
retrieves its controls from it.

### The geometric path

```text
sheet render
   → viewports.py       PDF clip/scissor rects segment the sheet into sub-drawings
   → vision.select_drawings  model picks the relevant sub-drawing by title
   → geometry.py        vector segments + text tokens, clipped to that viewport
   → boundary edges + per-boundary strip crops
   → vision.assess_boundary_strip   model reads dimensions from an isolated strip
   → certify_offsets    every model-read value must exist in the geometry token pool
   → governing_offset   min of non-"existing" offsets per boundary
   → height.py          ridge/wall RLs (elevations) − natural ground (survey), via AHD
   → compliance.py      RAG-retrieved controls + facts → per-boundary findings + citations
```

### The stated-value path

`manifest.py` builds a per-page list of salient text (ranked by font size), the model
fuzzy-matches the query against that manifest to pick pages, then reads the values off
the page images. Every number the model reports is then checked against the page's
extracted text — anything not present is flagged as invented rather than trusted.

### Module map

| Module | Responsibility |
| --- | --- |
| `viewports.py` | Segment a multi-drawing sheet by its own PDF clip rects |
| `geometry.py` | Vector primitives: segments, text tokens, `1:N` scale labels |
| `measure.py` | Deterministic distance at drawing scale (1 pt = 25.4/72 mm) |
| `candidates.py` | Dimension candidates as pure geometric facts (unlabelled) |
| `envelope.py` | Coloured building-envelope mask — **region hint only, never geometry** |
| `elevation.py` / `survey.py` | RL pools from elevations and the feature survey |
| `height.py` | Overall height and ResCode wall-height setback range (as a range, with a "marginal" verdict) |
| `vision.py` | All model calls: routing, page/drawing selection, feature identification |
| `verify.py` | Query-agnostic focused check: isolate → mark in red → one question at temp 0 |
| `pipeline.py` | Query → drawing → per-boundary setbacks |
| `compliance.py` | Setback facts + retrieved controls → cited compliance findings |
| `read_answer.py` | Generic read-and-compare for stated values |
| `triage.py` | Control checklist → GREENLIGHT / SEND TO PLANNER |
| `run_slice*.py` | Numbered exploratory slices, in development order — kept as a record of what was tried |

### Design rules

These constrain every technique in the spike:

1. **Geometry first.** The printed dimension is canonical; measured geometry validates
   it. If the drawing says 10800 and geometry measures 10854, report 10800 and treat
   the delta as a confidence signal.
2. **The model localises, code measures.** Vision calls return regions, page choices,
   and semantic labels — never a number that gets used unchecked. Model-read values are
   cross-certified against the extracted token pool.
3. **No drawing conventions.** Nothing keys off linetype, lineweight, hatching or
   colour. Anything that only works for one draughting office is rejected.
4. **Fail closed.** No generic signal → `UNDETERMINED` → the project routes to a human.
   Triage greenlights only when every control clears with margin.

`setback_extraction_recommendations.txt` records the production architecture this spike
is validating (evidence graph: boundary edge → dimension object → building element).

---

## Assets

`.gitignore` excludes `assets/`, `tests/`, `admin/` and `chroma_db/`, so a fresh clone
has no drawings or index. The geometry spike expects:

```text
assets/site_plan.pdf
assets/elevations_and_sections.pdf
assets/feature_survey.pdf
assets/plans.pdf              # full set, used by the drawings indexer
```

`tmp/` holds intermediate renders, crops and run logs.

---

## Tests

```sh
.venv/bin/pip install pytest      # not currently a declared dependency
.venv/bin/python -m pytest
```

`pyproject.toml` sets `pythonpath = ["."]` so `src` imports resolve. Note that `tests/`
is git-ignored, so the suite is local-only.

---

## Known rough edges

- `pyproject.toml` requires Python `>=3.14`, but the checked-in `.venv` is 3.13.14.
  One of the two should move.
- `requirements.txt` and `pyproject.toml` list dependencies separately and can drift.
- `[tool.pytest.ini_options]` is configured but `pytest` is declared in neither
  dependency list, so `python -m pytest` fails on a clean install.
- `src/main.py`'s `if __name__ == "__main__"` block is commented out — there is no
  console entry point.
- `src/llm/interace.py` is a typo for `interface.py`.
- `src/drawings/schemas.py` exports `PageFeautres` (typo for `PageFeatures`), which
  collides conceptually with `manifest.PageFeatures` in the spike.
- `run_slice*.py` files are exploratory and unpruned; only `run_auto.py` is a
  supported entry point.
