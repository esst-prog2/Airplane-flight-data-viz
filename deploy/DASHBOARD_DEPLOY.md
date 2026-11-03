# Live dashboard deploy (VPS)

Bring up the live dashboard on the VPS behind Caddy with automatic HTTPS. All
commands run on the VPS (`ssh root@65.21.0.244`, repo at `/root/flights`). The
collector, Postgres and the mart cron are untouched. The offline (Streamlit
Cloud) form is a separate, later step (built from the final data at collection
end).

Architecture:

    browser --HTTPS/443--> caddy --http--> dashboard (Streamlit :8501)
                                              |  reads
                                              v
                                    api (FastAPI) --flights_ro--> postgres
                                 (dashboard falls back to a direct DB read if api is down)

## 1. Pull the latest code

```bash
cd /root/flights
git fetch upstream && git merge --ff-only upstream/main
```

## 2. Create the read-only role and its login

Apply the role grants, then give it a login password and record that password in
`.env` as `FLIGHTS_RO_PASSWORD` (the `api`/`dashboard` connect as `flights_ro`).
Pick a strong password and use the **same** value in both places.

```bash
# grants (CONNECT/USAGE/SELECT on mart only)
docker compose exec -T postgres psql -U flights -d flights -v ON_ERROR_STOP=1 < sql/roles/flights_ro.sql

# give it a login + password (replace <STRONG_PASSWORD>)
docker compose exec -T postgres psql -U flights -d flights \
  -c "ALTER ROLE flights_ro WITH LOGIN PASSWORD '<STRONG_PASSWORD>';"
```

Add to `.env` (same password):

```
FLIGHTS_RO_PASSWORD=<STRONG_PASSWORD>
```

## 3. Free domain (DuckDNS)

1. Sign in at https://www.duckdns.org (GitHub/Google), create a subdomain, e.g. `flights-ce`.
2. Point it at the VPS IP (once is enough for a static IP):

```bash
curl "https://www.duckdns.org/update?domains=flights-ce&token=<YOUR_DUCKDNS_TOKEN>&ip=65.21.0.244"
# expect: OK
```

3. Add to `.env`:

```
DASHBOARD_DOMAIN=flights-ce.duckdns.org
```

Check DNS resolves to the VPS before continuing:

```bash
getent hosts flights-ce.duckdns.org    # should show 65.21.0.244
```

## 4. Open the HTTP/HTTPS ports

Caddy needs 80 (for the Let's Encrypt challenge) and 443 reachable from the internet.

```bash
# if ufw is in use:
ufw allow 80 && ufw allow 443 && ufw status
```

If the VPS uses the Hetzner Cloud firewall instead, allow TCP 80 and 443 there.

## 5. Build and start the dashboard stack

```bash
docker compose up -d --build api dashboard caddy
docker compose ps
```

Caddy obtains the TLS certificate on first start; watch it succeed:

```bash
docker compose logs --tail=30 caddy    # look for "certificate obtained successfully"
```

## 6. Verify

```bash
curl -I https://flights-ce.duckdns.org/    # expect HTTP/2 200
```

Then open `https://flights-ce.duckdns.org/` in a browser — it should show the
dashboard defaulting to the latest fully-covered day. The TLS certificate is
stored in the `caddy_data` volume and renews automatically.

## Troubleshooting

- **Cert not issued** — DNS must resolve to the VPS and ports 80/443 be open before Caddy can pass the Let's Encrypt challenge. Fix DNS/firewall, then `docker compose restart caddy`.
- **Dashboard shows a connection error** — check the API: `docker compose logs --tail=30 api`. The dashboard also falls back to a direct read-only DB read, so a transient API issue should not blank the page.
- **`password authentication failed for "flights_ro"`** — the password in `.env` (`FLIGHTS_RO_PASSWORD`) must match the one set in the `ALTER ROLE` in step 2; re-run the `ALTER ROLE` or fix `.env`, then `docker compose up -d api dashboard`.
- **Rebuild after a code change** — `git merge --ff-only upstream/main` then `docker compose up -d --build api dashboard`.
