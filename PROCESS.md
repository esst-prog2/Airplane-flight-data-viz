# Promo-page process log

A step-by-step record of building the project's GitHub Pages promo page (a class
exercise). One row per step: the step, what the tool did, and what I decided.

| Step | What the tool did | What I decided |
| --- | --- | --- |
| 1. Setup | Confirmed Impeccable (`pbakaus/impeccable`) is installed via `/plugin`, and the gstack skill suite (`garrytan/gstack`) is cloned into `~/.claude/skills/gstack` (its `/office-hours` content skill is reached through the `/gstack` router). Started this `PROCESS.md` and the convention of committing and logging a row after each step. | Use the course tools (gstack for content, Impeccable for the look). The page and this log live in the main repo (`esst-prog2/Airplane-flight-data-viz`), published via GitHub Pages. Nothing personal goes on the page. |
| 2. Content (gstack `/office-hours`) | gstack's scripts are blocked by the session sandbox, so office-hours ran in its documented degraded mode (no telemetry/brain). Ran the office-hours interview method and wrote `docs/promo-content.md`: a two-audience content brief (a casual live-map section and a short technical taste: continuous collection, staging, a Kimball star schema on Postgres/Docker) with CTAs to the live dashboard and the GitHub repo. | Broad audience: a casual part (just the live map) plus a technical taste for developers, with the full GitHub project for anyone who wants more. One takeaway in two parts: a simple map with real data behind it, and the data-engineering keywords. Include the GitHub link. Keep the title "Central European Air Traffic". Approved the draft with no changes. |
