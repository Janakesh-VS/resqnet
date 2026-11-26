import os
import sys
import webbrowser
import uvicorn

# Add current dir and venv site-packages to sys.path
BASE_DIR = os.path.dirname(os.path.abspath(__file__))
if BASE_DIR not in sys.path:
    sys.path.insert(0, BASE_DIR)

VENV_PKGS = os.path.join(BASE_DIR, ".venv", "Lib", "site-packages")
if os.path.exists(VENV_PKGS) and VENV_PKGS not in sys.path:
    sys.path.append(VENV_PKGS)

from resqnet.seed import seed_tamil_nadu_data
from resqnet.api import app

def main():
    print("=" * 60)
    print("ResQNet: Agentic AI-Powered Disaster Relief & Animal Emergency Response")
    print("K! Hacks 4.0 Demo - Team Obsidyne")
    print("=" * 60)
    print("1. Initializing and seeding SQLite database with Tamil Nadu flood scenario...")
    seed_tamil_nadu_data()

    print("\n2. Launching FastAPI + React PWA Server on http://127.0.0.1:8000 ...")
    print("   - Coordinator Dashboard: http://127.0.0.1:8000")
    print("   - API Documentation:     http://127.0.0.1:8000/docs")
    print("   - Live Leaflet OSM Map:  Included in Dashboard")
    print("   - Offline Citizen Queue: Active with toggle")
    print("=" * 60)

    uvicorn.run(app, host="127.0.0.1", port=8000, log_level="info")

if __name__ == "__main__":
    main()
