# Airplane-flight-data-viz

Central European air traffic: building a history the API does not keep

The OpenSky Network API tells you what is in the air right now. It does not tell you what was in the air last Tuesday. This project polls that live feed on a schedule, lands every snapshot, stitches the snapshots into flights, and turns them into a queryable warehouse — so questions about traffic patterns over time in this region can be asked at all.

1. The demo

I open a terminal and run docker compose up -d. Three containers start: Postgres, the collector, and the dashboard. I run flights ingest --once. It fetches the current air picture over the Central European bounding box, writes 480 raw aircraft states, and prints what it refused: 12 records with no position, 3 with an altitude above 60,000 ft, all of them in the rejects table with a reason. I run flights build. It rebuilds the star schema and prints 1,240 flight segments over the last 24 hours, 89% of them matched to a known aircraft type. I open localhost:8501, pick yesterday, and the map shows traffic density as 3D hexagons over the region. The daily curve has a visible notch between 03:00 and 04:00 — the collector was down for an hour, and the same gap is in the data-quality table underneath.

2. The shape
in           the OpenSky /states/all endpoint, one snapshot per poll,
             bounded to a fixed Central European box

out          a star schema of flight segments in Postgres, an hourly
             data-quality table, and a map dashboard over both

in between   land each snapshot raw and unvalidated; clean, type and
             de-duplicate it; stitch consecutive snapshots of the same
             aircraft into flight segments; join to aircraft and
             airport catalogues
3. The size

The first useful version does this, and does it with a single day of collected data:

polls the API on a schedule and lands raw snapshots without losing a run to a malformed response or an HTTP error
rejects bad records into a separate table with a reason instead of failing
builds a cleaned staging layer and a normalised star schema with real keys
stitches position snapshots into flight segments
records hourly collection coverage so gaps are visible rather than silent
serves a map and a daily traffic curve from the warehouse

It explicitly does not do this term:

no prediction of anything — no delay model, no ETA, no ML layer
no inference of origin and destination airports from the track
no real-time view; resolution is the poll interval, and the dashboard reads batch tables
no second region and no change to the bounding box once collection starts
no backfill of any period before day one, because the API does not offer it
no public write access, no user accounts, no Kubernetes

The warehouse is useful after one day. Every additional week makes the seasonal questions answerable, but nothing in the first version depends on the weeks arriving.

4. How we would know it works

Three behaviours a test could check:

Given a snapshot in which an aircraft record has a null latitude or longitude, that record lands in the rejects table with reason missing_position and the run still completes and commits the remaining records.
Given two polls whose time windows overlap and which both contain the same aircraft at the same reported timestamp, the staging table holds one row for it, not two.
Given an aircraft whose 24-bit address is absent from the aircraft catalogue, the flight segment is still created and resolves to the unknown member of the aircraft dimension, rather than failing on the foreign key.
5. What could stop this
No backfill. Every week of history costs a week of wall-clock time. If collection starts late or dies silently, that period is gone. Mitigated by starting collection in week three and alerting after three consecutive failed runs.
API access. OpenSky moved to OAuth2 client credentials in March 2026. Access is free for non-commercial and research use but metered by a daily credit budget, and the terms could change mid-term. The raw landing table is the hedge: once a snapshot is stored it is mine regardless.
Unknown catalogue coverage. The share of aircraft addresses that resolve to a known type and operator is not known until measured. If it is low, the operator and fleet analysis weakens. It gets measured in week four and reported as a number either way.
No ground truth for segmentation. There is no label saying where one flight ends and the next begins; the rule is mine to define and defend. Spot checks against public flight-tracking sites, and the rule stated explicitly rather than buried.
Techniques not yet attempted: running Docker Compose on a rented server, TLS behind a reverse proxy, and a workflow orchestrator. Each is a first for me.

Data provenance. OpenSky Network state vectors, free for non-commercial and research use. Aircraft metadata from the same source; airport reference data from OurAirports, public domain. No personal data is involved — aircraft registrations are public records — so everything can be shown in class.


## Setup

Secrets are not in the repository. Copy `.env.example` to `.env`
and fill in your own values:

    cp .env.example .env

You need an OpenSky account and an API client
(Account page -> create API client) for the credentials.

Then:

    docker compose up -d
