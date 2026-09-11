import time
import traceback

import ingest

INTERVAL = 120  # masodperc

print(f"Collector indul, {INTERVAL} masodpercenkent kerdez.")

while True:
    started = time.time()
    try:
        ingest.main()
    except SystemExit:
        pass
    except Exception:
        traceback.print_exc()

    elapsed = time.time() - started
    time.sleep(max(0, INTERVAL - elapsed))