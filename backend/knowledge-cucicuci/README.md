# Knowledge base

Business documents the assistant answers from (RAG). The ingestion script splits each file
into chunks at `##` headings, embeds them, and stores them in pgvector.

## Rules for writing documents

1. **Only confirmed facts.** If something isn't confirmed by the owner, leave it out. The
   assistant hands unanswered questions to a human instead of guessing, and they show up in
   the dashboard as gaps to fill.
2. **No prices.** Prices live in the database (`services` table, loaded by `app/seed.py`).
   The ingestion script generates the price-list text from the database, so there is one
   source of truth. A test fails if a document here contains `RM` amounts.
3. **One topic per `##` section.** Each section becomes one chunk and must make sense on its
   own, so repeat the subject ("Carpets are returned in 5-7 days") rather than writing
   "They are returned...".
4. **English, plus the Malay words customers use** (e.g. "cuci karpet", "tilam"). Embeddings
   are multilingual and the assistant replies in the customer's language, so one version of
   each fact is enough.

## Front matter

Each document starts with:

```
---
title: Short human-readable title
---
```

The title is shown as the source when the assistant cites a document.
