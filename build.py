from __future__ import annotations

import argparse
import json
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

import proceedings_build as pb  # noqa: E402


def build_parser() -> argparse.ArgumentParser:
    common = argparse.ArgumentParser(add_help=False)
    common.add_argument("--force", action="store_true", help="Rebuild the selected stage(s) regardless of timestamps.")
    common.add_argument("--version", default=pb.VERSION, help="Pipeline version tag for validation purposes.")
    parser = argparse.ArgumentParser(
        prog="build.py",
        description="Rebuild the APCOT 2026 proceedings pipeline.",
        epilog="Use `python build.py <stage>` to rebuild one stage, or `python build.py all` for the full pipeline.",
        formatter_class=argparse.RawDescriptionHelpFormatter,
        parents=[common],
    )
    subparsers = parser.add_subparsers(dest="command")

    all_parser = subparsers.add_parser("all", help="Run every stage in order.", parents=[common])
    all_parser.set_defaults(command="all")

    for stage in pb.PIPELINE_STAGES:
        stage_parser = subparsers.add_parser(stage.name, help=stage.description, parents=[common])
        stage_parser.set_defaults(command=stage.name)

    stages_parser = subparsers.add_parser("stages", help="List available pipeline stages.", parents=[common])
    stages_parser.set_defaults(command="stages")
    return parser


def print_stage_list() -> None:
    for stage in pb.PIPELINE_STAGES:
        print(f"{stage.name}: {stage.description}")


def print_summary(results: list[tuple[str, dict[str, object]]]) -> None:
    for stage_name, result in results:
        print(f"{stage_name}: {json.dumps(result, ensure_ascii=False)}")


def main(argv: list[str] | None = None) -> int:
    parser = build_parser()
    args = parser.parse_args(argv)

    if args.version != pb.VERSION:
        raise SystemExit(f"Unsupported version: {args.version}. This build script is pinned to {pb.VERSION}.")

    if args.command == "stages":
        print_stage_list()
        return 0

    if args.command in (None, "all"):
        results = pb.run_pipeline(force=args.force)
        print_summary(results)
        return 0

    result = pb.run_stage(args.command, force=args.force)
    print(json.dumps(result, ensure_ascii=False, indent=2))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
