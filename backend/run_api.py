from __future__ import annotations

import sys
from pathlib import Path

import uvicorn


def main() -> None:
    backend_dir = Path(__file__).resolve().parent
    src = backend_dir / "src"
    sys.path.insert(0, str(src))
    uvicorn.run("meituan_agent.api.main:app", host="127.0.0.1", port=8000, reload=False)


if __name__ == "__main__":
    main()

