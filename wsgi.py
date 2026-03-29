"""WSGI entry point for PulpIQ web app."""

import sys
from pathlib import Path

# Ensure src/ is on the path
sys.path.insert(0, str(Path(__file__).resolve().parent / "src"))

from webapp import create_app

app = create_app()

if __name__ == "__main__":
    app.run(debug=True, port=5000)
