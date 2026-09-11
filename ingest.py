import json
import os
import sys
import time

import psycopg
import requests
from dotenv import load_dotenv

load_dotenv()

TOKEN_URL = "https://auth.opensky-network.org/auth/realms/opensky-network/protocol/openid-connect/token"
STATES_URL = "https://opensky-network.org/api/states/all"
BBOX = {"lamin": 45.0, "lomin": 12.0, "lamax": 50.0, "lomax": 23.0}

_token = None
_token_expires_at = 0.0


def get_token():
    """Tokent ad vissza, es csak akkor ker ujat, ha a regi mar lejaroban van."""
    global _token, _token_expires_at

    if _token and time.time() < _token_expires_at:
        return _token

    response = requests.post(
        TOKEN_URL,
        data={
            "grant_type": "client_credentials",
            "client_id": os.environ["OPENSKY_CLIENT_ID"],
            "client_secret": os.environ["OPENSKY_CLIENT_SECRET"],
        },
        timeout=30,
    )
    response.raise_for_status()
    payload = response.json()

    _token = payload["access_token"]
    # 60 masodperccel a tenyleges lejarat elott mar ujat kerunk
    _token_expires_at = time.time() + payload.get("expires_in", 1800) - 60
    return _token


def fetch_states():
    """Egy pillanatkepet ker le a bounding boxrol."""
    response = requests.get(
        STATES_URL,
        headers={"Authorization": f"Bearer {get_token()}"},
        params=BBOX,
        timeout=30,
    )
    response.raise_for_status()
    return response.json()


def store(data):
    """A pillanatkep minden gepet beirja a raw tablaba."""
    api_time = data["time"]
    states = data.get("states") or []

    if not states:
        return 0

    rows = [(api_time, json.dumps(state)) for state in states]

    with psycopg.connect(os.environ["DATABASE_URL"]) as conn:
        with conn.cursor() as cur:
            cur.executemany(
                "INSERT INTO raw.state_snapshot (api_time, payload) VALUES (%s, %s)",
                rows,
            )
    return len(rows)


def main():
    try:
        data = fetch_states()
    except requests.RequestException as exc:
        print(f"API hiba: {exc}", file=sys.stderr)
        sys.exit(1)

    count = store(data)
    print(f"api_time={data['time']}  beirt sorok: {count}")


if __name__ == "__main__":
    main()