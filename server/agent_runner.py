"""Restricted one-shot Hermes entry point for Interfaze product runs."""
from __future__ import annotations

import argparse
from collections.abc import Sequence

from hermes_cli.oneshot import run_oneshot

from .run_types import READ_ONLY, execution_spec


EXECUTABLE = "interfaze-agent-run"


def build_command(
    run_type: str,
    prompt: str,
    *,
    skill: str | None = None,
    model: str | None = None,
) -> list[str]:
    command = [EXECUTABLE, "--run-type", run_type, "--prompt", prompt]
    if skill:
        command.extend(["--skill", skill])
    if model:
        command.extend(["--model", model])
    return command


def _parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(prog=EXECUTABLE)
    parser.add_argument("--run-type", required=True, choices=sorted(READ_ONLY))
    parser.add_argument("--prompt", required=True)
    parser.add_argument("--skill", required=True)
    parser.add_argument("--model")
    return parser


def main(argv: Sequence[str] | None = None) -> int:
    args = _parser().parse_args(argv)
    skill, toolsets = execution_spec(args.run_type, args.skill)
    return run_oneshot(
        args.prompt,
        model=args.model,
        skills=[skill],
        toolsets=toolsets,
    )


if __name__ == "__main__":
    raise SystemExit(main())
