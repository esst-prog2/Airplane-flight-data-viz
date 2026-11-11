<!-- impeccable:product-schema 1 -->
# Product

Promo / landing page for the **Central European Air Traffic** project
(Airplane-flight-data-viz): a live public dashboard backed by a data-engineering
pipeline. This record covers the promo page only, not the dashboard app.

## Platform
web

## Stack
Plain static HTML/CSS, no build step (user brief). Deploy target: GitHub Pages
(project page under `esst-prog2.github.io/Airplane-flight-data-viz`). No backend;
the page links out to the live dashboard and the GitHub repo.

## Users
Broad, two kinds arriving from a shared or portfolio link:
- A **casual visitor** curious about air traffic who just wants to see the live map.
- A **developer** scanning for a short technical taste (data engineering) before
  deciding whether to open the full GitHub project.

## Product Purpose
Get a casual visitor to open the live dashboard, and give a developer a short,
credible technical taste (then the repo). It is a front door, not the README.

## Positioning
One air-traffic project with a genuinely live, public dashboard and a real
data-engineering pipeline behind it. Honest and concrete, not a generic template.
Tagline the project owns: "a history the API does not keep."

## Operating Context
A public web page, scanned quickly on both desktop and phone, reached from a
class submission, a portfolio, or a shared link. Success = a click through to the
live dashboard; secondary = a click to GitHub.

## Capabilities and Constraints
Static page, no backend or login. Primary action: open the live dashboard
(https://flights-ce.duckdns.org). Secondary: the GitHub repo
(https://github.com/esst-prog2/Airplane-flight-data-viz). Must be responsive
(phone + desktop). Nothing personal on the page (no name, no email).

## Brand Commitments
None pre-existing; the visual world is open (new-work decides it). Subject matter:
flight / air traffic / maps over Central Europe; data engineering.

## Evidence on Hand
Real numbers from the project: 7.7M+ position rows; collecting every 2 minutes
since 2026-09-17; bounding box lat 45-50, lon 12-23; a Kimball star schema in
PostgreSQL rebuilt hourly; stack Python / PostgreSQL / Docker / FastAPI /
Streamlit / Caddy. The live dashboard and the GitHub repo are both reachable.
Approved copy lives in `docs/promo-content.md`.

## Product Principles
- Honest: real numbers and real links only, no invented claims.
- Two audiences on one page: a casual live-map hero, plus a short technical taste.
- The live map is the hero; the technical section is a credible taste, not the README.

## Accessibility & Inclusion
Legible type and strong contrast, keyboard-reachable links, responsive from phone
to desktop, and fully usable without a login.
