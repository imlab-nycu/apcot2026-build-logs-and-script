# APCOT 2026 Build Logs and Script

This repository contains APCOT 2026 proceedings build artifacts and the reusable build scripts.

For the step-by-step workflow and the matching files for each stage, see [PROCEEDINGS_WORKFLOW.md](PROCEEDINGS_WORKFLOW.md).

## Rebuild

1. Create or activate a Python 3.12 virtual environment.
2. Install dependencies with `pip install -r requirements.txt`.
3. Run `python build.py` or `python build.py all` to rebuild the full pipeline, `python build.py stages` to list the available stages, or `python build.py <stage>` for a single stage such as `manifest`, `toc`, or `final`.
4. Add `--force` to any command to regenerate that stage or pipeline group regardless of timestamps.

The build script uses the current HTML index, the cleaned manifest CSV, the TOC PDF, the front matter PDF, and the abstract PDFs under `APCOT_Abstract/`.

Included files:
- Build log files under `derived/` matching `*_build_log.json`
- `build.py`
- `make_public_v10b_toc.py`
- `proceedings_build.py`
- `requirements.txt`
