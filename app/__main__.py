"""Entrypoint:

    python -m app api        # control-plane API + dashboard (runs the controller)
    python -m app migrate    # create schema
"""
from __future__ import annotations
import sys
from .config import cfg
def main():
    if len(sys.argv) < 2:
        print(__doc__); sys.exit(1)
    cmd = sys.argv[1]
    if cmd == "api":
        import uvicorn
        uvicorn.run("app.api:app", host=cfg.api_host, port=cfg.api_port, log_level="warning")
    elif cmd == "migrate":
        from .db import Store
        s = Store(cfg.database_url); s.migrate(); s.close(); print("schema applied")
    else:
        print(f"unknown command: {cmd}"); print(__doc__); sys.exit(1)
if __name__ == "__main__":
    main()
