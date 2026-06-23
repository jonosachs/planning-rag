# Planning-RAG

RAG app using Victorian planning scheme data. \
Base API path: <https://api.app.planning.vic.gov.au/planning/v2/schemes/>

## Pipeline

- Seed db: ingest -> chunk -> embed -> vector store 
- Query: embed query -> retrieve context (vector similarity) -> prompt (query + context) -> response 

## Requirements

- Google Gemini API key saved to .env as `GEMINI_API_KEY`
- gemini-embedding-001 for embedding
- gemini-3-flash-preview for response generation
- `pip install -r requirements.txt` 

## Sample interaction

```txt
Query: what are the high level overshadowing requirements?

Answer: High-level overshadowing requirements for new development focus on protecting secluded private open space. Under VPP Standard E4-1, development should ensure that at least 50 per cent (or 25 square metres with a minimum dimension of 3 metres, whichever is less) of the secluded private open space is not overshadowed for a minimum of five hours between 9 am and 3 pm on 22 September. If existing sunlight is already below this requirement, the amount of sunlight must not be further reduced. Decision-making includes evaluating the impact on amenity, the duration and timing of available sunlight, and how a reduction affects the existing use of the space.

The following are identified as site-specific controls:
- Wellington Street (Areas 3B and 3C): Development must not cast a shadow beyond the southern kerb-line between 10am and 3pm on 21 September; this cannot be varied.
- Wellington Street (Area 3A): Development should not cast a shadow beyond the southern kerb-line between 10am and 3pm on 21 September.
- Carlisle Street: Development must not cast a shadow beyond the southern kerb-line between 10am and 3pm on 21 September; this cannot be varied.
- Inkerman Street: Development should not cast a shadow beyond the southern kerb-line between 10am and 3pm on 21 September.

Citations:
1 ['scheme_id: port', 'ordinance_id: 20578523', 'chunk_index: 0', 'title: 57.04-1 Overshadowing secluded private open space objective']
2 ['scheme_id: port', 'ordinance_id: 20578443', 'chunk_index: 1', 'title: 55.04-3 Overshadowing secluded open space objective']
3 ['scheme_id: port', 'ordinance_id: 20578407', 'chunk_index: 1', 'title: 54.04-3 Overshadowing secluded open space objective']
4 ['scheme_id: port', 'ordinance_id: 20577769', 'chunk_index: 0', 'title: 2.7 Overshadowing']
5 ['scheme_id: port', 'ordinance_id: 20577653', 'chunk_index: 0', 'title: 2.7 Overshadowing']
```
