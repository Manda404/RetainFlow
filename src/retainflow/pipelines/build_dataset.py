"""CLI entrypoint for building the local RetainFlow dataset."""

from __future__ import annotations

from retainflow.generation.synthetic import parse_args, run_generation


def main() -> None:
    run_generation(parse_args())


if __name__ == "__main__":
    main()
