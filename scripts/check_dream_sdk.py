import os

from dotenv import load_dotenv

load_dotenv()

try:
    import dream
except ImportError:
    print("ERROR: Dream SDK missing. Run: python -m pip install -e '.[dev]'")
    raise SystemExit(1)

if not os.getenv("DREAM_API_KEY"):
    print("ERROR: DREAM_API_KEY is not set in this PowerShell session.")
    print('Set it with: $env:DREAM_API_KEY = "dl_live_your_key"')
    raise SystemExit(1)

try:
    client = dream.DreamClient()
    client.close()
except Exception as exc:  # noqa: BLE001 - report any SDK init failure
    print(f"ERROR: DreamClient initialization failed: {type(exc).__name__}: {exc}")
    raise SystemExit(1)

print(f"OK: imported dream SDK version {getattr(dream, '__version__', 'unknown')}")
print("OK: DreamClient initialized and closed. No inference request was sent.")
