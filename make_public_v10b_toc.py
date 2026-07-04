from __future__ import annotations

import os
import sys
from pathlib import Path


ROOT = Path(__file__).resolve().parent


def bootstrap() -> None:
    try:
        import proceedings_build  # noqa: F401
    except ImportError:
        venv_python = ROOT / ".venv_apcot" / "bin" / "python"
        if venv_python.exists() and Path(sys.executable).resolve() != venv_python.resolve():
            os.execv(str(venv_python), [str(venv_python), *sys.argv])
        raise


bootstrap()

import json

import proceedings_build as pb  # noqa: E402


def main() -> None:
    summary = pb.build_toc_pdf(pb.MANIFEST_CSV, pb.TOC_PDF, pb.TOC_BUILD_LOG)
    print(json.dumps(summary, ensure_ascii=False, indent=2))


if __name__ == "__main__":
    main()