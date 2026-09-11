import os
import requests
from dotenv import load_dotenv

load_dotenv()

TOKEN_URL = "https://auth.opensky-network.org/auth/realms/opensky-network/protocol/openid-connect/token"
STATES_URL = "https://opensky-network.org/api/states/all"

# Közép-Európa: Ausztria, Magyarország, Csehország, Szlovákia és környékük
BBOX = {"lamin": 45.0, "lomin": 12.0, "lamax": 50.0, "lomax": 23.0}

# 1. Token kérése
token_response = requests.post(
    TOKEN_URL,
    data={
        "grant_type": "client_credentials",
        "client_id": os.environ["OPENSKY_CLIENT_ID"],
        "client_secret": os.environ["OPENSKY_CLIENT_SECRET"],
    },
    timeout=30,
)
token_response.raise_for_status()
token = token_response.json()["access_token"]
print("Token megvan.")

# 2. Pillanatkép lekérése
states_response = requests.get(
    STATES_URL,
    headers={"Authorization": f"Bearer {token}"},
    params=BBOX,
    timeout=30,
)
states_response.raise_for_status()
data = states_response.json()

states = data.get("states") or []
print(f"Idobelyeg: {data['time']}")
print(f"Gepek szama a dobozban: {len(states)}")
if states:
    print(f"Elso gep: {states[0]}")