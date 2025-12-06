"""
Compatibility wrapper for WB-BIDDER v2 backend.

The full FastAPI implementation resides in wb_bidder_v2.backend_v2.backend_v2.
This module keeps the historical entrypoint usable while ensuring the logic
is sourced from the new architecture.
"""

from wb_bidder_v2.backend_v2.backend_v2 import *  # noqa: F401,F403


if __name__ == "__main__":
    import uvicorn

    uvicorn.run(app, host="127.0.0.1", port=8002, reload=True)
