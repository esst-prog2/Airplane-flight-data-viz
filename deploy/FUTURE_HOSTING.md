# Future hosting plan (decide ~Feb 2027)

Planning note for when the current Hetzner prepaid credit runs low. **No action is
needed before then** — collection keeps running and the live dashboard stays honest.

## Where we are

- The whole stack runs on one **Hetzner Cloud VPS** (`root@65.21.0.244`, repo at
  `/root/flights`): Postgres + the collector + the hourly mart cron + the read-only
  FastAPI + the Streamlit dashboard + Caddy/HTTPS, all via `docker compose`.
- Collector running since **2026-09-17**; the mart is **7.7M+ position rows and
  growing** (the full Postgres DB, with `raw`, is several GB).
- Cost: **~6.6 EUR/month**. Prepaid credit was **~€21** as of 2026-11-23, i.e.
  roughly **3 months of runway** (into ~Feb 2027). Covers the Dec 1 and Dec 15
  presentations comfortably.

## Two different artifacts (do not confuse them)

| Artifact | What it is | Size | Used for |
| --- | --- | --- | --- |
| **`pg_dump`** | a full backup of the Postgres DB | several GB | migrating the warehouse to another server (restore and keep running) |
| **SQLite snapshot** | pre-aggregated per-day dashboard data (`dashboard/build_snapshot.py`) | a few MB | the offline dashboard form on Streamlit Community Cloud |

## Free-tier reality (checked 2026-11, verify before acting — limits change)

| Service | Free allowance | Fits our warehouse? |
| --- | --- | --- |
| **Oracle Cloud "Always Free" VM** | an always-on Linux VM: ARM Ampere A1 ~2–4 OCPU / 12–24 GB RAM + **200 GB** block storage | **Yes** — the whole Docker stack fits and can run continuously |
| **Supabase** (managed Postgres) | 500 MB DB; **pauses after ~1 week** idle | No — far too small; pausing kills a live collector |
| **Neon** (managed Postgres) | 1 GB/project; compute auto-suspends after 5 min idle | No — too small for a continuously growing warehouse |
| **Streamlit Community Cloud** | runs a Streamlit app (~1 GB RAM/app, 1 private app); sleeps after ~12 h no traffic | Yes for the **dashboard app** (it only reads data from somewhere else) |

Key point: managed free Postgres (Supabase/Neon) is **too small** for the full mart.
A genuinely free way to keep **continuous live collection** needs a **free always-on
VM** → **Oracle Always Free** (200 GB fits everything; no data split needed).
Caveats: Oracle ARM free capacity can be hard to get, a card is required to sign up,
and the ARM allowance was reportedly halved in 2026 (still enough). Verify in the OCI
console before relying on numbers.

## Options

### A) Migrate the whole stack to a free VM (Oracle Always Free) — keep it live & continuous
- One free always-on VM runs the **same** `docker compose` stack as Hetzner.
- Migrate: `pg_dump` on Hetzner → restore on Oracle → repoint the DuckDNS domain to
  the new IP → collection continues.
- Result: **Sept → today, one source, continuous, live.** No split, no combining.
  The page/video "Live now" claims stay true.
- Cost: free. Downside: Oracle setup is fiddlier than Hetzner; ARM capacity and
  account strictness are real risks.

### B) Freeze into a portfolio piece (Streamlit Cloud + SQLite snapshot) — simplest, not live
- Build one **frozen SQLite snapshot** (a few MB) of the whole collected period and
  deploy the offline dashboard on **Streamlit Community Cloud** (free, public, no login).
- Result: a permanent, zero-maintenance public page showing every collected day — but
  **frozen** (no new data). Switch the page/video "live" wording to past tense
  ("recorded Sept–Nov/Dec 2026"). This is the original `dashboard-build` task 5.3.
- Cost: free. Downside: no ongoing collection.

### C) Combine two sources (only if forced to split)
- Needed only if there is **no** full free VM: keep the old period as a frozen snapshot
  and collect the new period into a small free Postgres (Neon/Supabase). Because those
  cap at ~1 GB, the "new" side can only hold a **rolling recent window**, not grow
  forever.
- The dashboard **can** show both as one continuous view: the `DataSource` abstraction
  (`dashboard/datasource.py`) already has four backends (DB / API / snapshot / fallback);
  add a `CombinedSource` that reads old dates from the snapshot and new dates from the
  live DB and sums the KPIs. Buildable, but the most complex and fragile path.
- **Avoid this by choosing A** (one VM, everything fits, one source).

## Recommendation

- **Want it to stay live & continuous for free:** Option **A** (Oracle Always Free) —
  migrate the whole stack, no split, no combining.
- **A stable, permanent portfolio piece is enough:** Option **B** (freeze → Streamlit
  Cloud) — simplest and most robust.
- **Honest middle ground:** Hetzner is only ~6.6 EUR/month. For a portfolio piece worth
  keeping, just **staying on Hetzner** may beat a fiddly free migration. Weigh "free but
  fiddly" (Oracle) vs "cheap but proven" (Hetzner).

## Next action

Revisit when the Hetzner balance runs low (~Feb 2027). Nothing to do before then.

## Sources (free-tier limits, 2026)

- Oracle Always Free: https://docs.oracle.com/iaas/Content/FreeTier/resourceref.htm ·
  2026 reduction: https://infoq.com/news/2026/07/oracle-cloud-free-tier-limits/
- Supabase: https://supabase.com/docs/pricing ·
  pausing: https://supabase.com/kb/faqs/platform/free-project-pausing
- Neon: https://neon.com/faqs/free-plan-limits-and-quotas ·
  1 GB: https://neon.com/blog/neon-free-plan-1-gb-per-project
- Streamlit Community Cloud: https://docs.streamlit.io/deploy/streamlit-community-cloud/status
