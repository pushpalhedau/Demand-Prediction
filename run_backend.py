"""
Convenience launcher — adds project root to sys.path then starts FastAPI.
Run as: python run_backend.py
"""
import sys
from pathlib import Path

# Ensure project root is on Python path regardless of where you run from
ROOT = Path(__file__).resolve().parent
if str(ROOT) not in sys.path:
    sys.path.insert(0, str(ROOT))

import uvicorn

if __name__ == "__main__":
    uvicorn.run(
        "backend.main:app",
        host="0.0.0.0",
        port=8000,
        reload=True,
        reload_excludes=["datasets/*", "models/*", "*.db"],
        log_level="info",
    )
