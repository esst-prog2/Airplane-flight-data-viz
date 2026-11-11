# Promo page content

The approved copy for the project's GitHub Pages promo page. Content only; the
look is built separately (Impeccable). Two audiences: a casual visitor who just
wants the live map, and a developer who wants a short technical taste before the
full GitHub project. Nothing personal appears on the page.

Links:
- Live dashboard: https://flights-ce.duckdns.org
- GitHub repository: https://github.com/esst-prog2/Airplane-flight-data-viz

---

## Hero (for everyone)

**Title:** Central European Air Traffic

**Subtitle:** A live map of the planes over Central Europe, backed by a data
warehouse that has been quietly recording the sky every two minutes since
September 2026.

**Primary button:** Open the live dashboard → (https://flights-ce.duckdns.org)

**Secondary button:** See the code on GitHub → (https://github.com/esst-prog2/Airplane-flight-data-viz)

## What you see (casual)

Pick any day and explore the sky over Central Europe:

- a 3D hexagon map of where the traffic was,
- a daily curve of how many aircraft were up, hour by hour,
- aircraft types and countries,
- and where the collection had gaps.

No login, runs in your browser.

## Under the hood (a technical taste, for developers)

The map is the easy part. Behind it is a small data-engineering pipeline:

- **Continuous collection** — polls the live OpenSky feed every 2 minutes over a
  fixed Central European box, landing every snapshot. A day not collected is lost
  for good.
- **Cleaned and organized** — raw snapshots are validated into a staging layer,
  then stitched into flights.
- **Star-schema warehouse** — a Kimball dimensional model in PostgreSQL (facts +
  dimensions), 7.7M+ position rows, rebuilt hourly.
- **Stack** — Python, PostgreSQL, Docker; served by FastAPI + Streamlit behind
  Caddy / HTTPS on a small VPS.

Want the details? The full project, design docs and SQL are on GitHub.

## Footer (calls to action)

- Live dashboard → https://flights-ce.duckdns.org
- GitHub repository → https://github.com/esst-prog2/Airplane-flight-data-viz

---

Facts used (from the project): 7.7M+ position rows; collecting since 2026-09-17;
bounding box lat 45-50, lon 12-23.
