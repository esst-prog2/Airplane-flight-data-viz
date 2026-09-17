import os
import time
import traceback

import requests

import ingest

INTERVAL = 120          # masodperc ket lekerdezes kozott
ALERT_AFTER = 3         # ennyi egymas utani hiba utan szolunk

WEBHOOK_URL = os.environ.get("ALERT_WEBHOOK_URL")


def alert(message):
    """Ertesitest kuld, ha van beallitva webhook."""
    if not WEBHOOK_URL:
        return
    try:
        requests.post(WEBHOOK_URL, json={"content": message}, timeout=10)
    except Exception:
        # Az ertesites hibaja soha ne allitsa meg a gyujtest
        traceback.print_exc()


print(f"Collector indul, {INTERVAL} masodpercenkent kerdez.")

consecutive_failures = 0
alerted = False

while True:
    started = time.time()

    try:
        ingest.main()
        if alerted:
            alert("A gyujtes ujraindult, megint jonnek az adatok.")
        consecutive_failures = 0
        alerted = False
    except SystemExit:
        consecutive_failures += 1
    except Exception:
        traceback.print_exc()
        consecutive_failures += 1

    if consecutive_failures >= ALERT_AFTER and not alerted:
        alert(f"A collector {consecutive_failures} egymas utani futasa elhasalt.")
        alerted = True

    elapsed = time.time() - started
    time.sleep(max(0, INTERVAL - elapsed))