"""
#############################################################################
### OpenAPI export file
###
### @file export_openapi.py
### @author Sebastian Russo
### @date 2026
#############################################################################

Writes the backend's OpenAPI schema to frontend/openapi.json, from which the
dashboard generates its TypeScript types (npm run gen:api). A backend test
fails when the committed schema no longer matches the API.

Usage (from the backend folder):
    python export_openapi.py
"""

#Native imports
import json
from pathlib import Path

#Other files imports
from main import app

"""VARIABLES-----------------------------------------------------------"""
OUTPUT_PATH = Path(__file__).resolve().parent.parent / "frontend" / "openapi.json"


"""METHODS-----------------------------------------------------------"""
def render_schema() -> str:
    """The OpenAPI schema as stable, pretty-printed JSON."""
    return json.dumps(app.openapi(), indent=2, sort_keys=True) + "\n"


if __name__ == "__main__":
    OUTPUT_PATH.write_text(render_schema(), encoding="utf-8")
    print(f"OpenAPI schema written to {OUTPUT_PATH}")
