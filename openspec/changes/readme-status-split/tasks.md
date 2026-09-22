# Tasks

## 1. Restructure README.md

- [x] 1.1 Add a "Status" section near the top that lists only what is built and runnable today (collector `ingest.py`/`run_loop.py`, `raw.state_snapshot` landing table, Docker Compose with `postgres` + `collector` services) and verify every item listed has matching code/config in the repo
- [x] 1.2 Move the existing "The demo", "The shape", "The size", "How we would know it works", and "What could stop this" content into a clearly labeled "Vision" (target scope) section, and verify no existing content is lost or altered in meaning — only re-labeled and re-sectioned
- [x] 1.3 Rewrite the Setup section to describe only the commands that work today (`docker compose up -d` starting Postgres + collector; no dashboard container, no `flights` CLI) and verify it matches `docker-compose.yaml` exactly
- [x] 1.4 Add an explicit note in the Status section stating that `ingest.py` and `run_loop.py` are complete and frozen — the collector is the project's one irreversible part — and verify the note is present and unambiguous

## 2. Review

- [x] 2.1 Read the full restructured README top to bottom and verify a first-time reader can tell, without checking the code, exactly what runs today versus what is planned
