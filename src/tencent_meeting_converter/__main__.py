"""Command-line interface for local transcript conversion."""

import argparse
from pathlib import Path
import sys

from .core import convert, format_clock


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("inputs", type=Path, nargs="+", metavar="INPUT")
    destination = parser.add_mutually_exclusive_group(required=True)
    destination.add_argument("-o", "--output", type=Path, metavar="FILE")
    destination.add_argument("-d", "--output-dir", type=Path, metavar="DIR")
    parser.add_argument("--format", choices=("srt", "vtt"), help="required with --output-dir")
    parser.add_argument("--tail-seconds", type=int, default=5, help="last group duration (default: 5)")
    args = parser.parse_args(argv)

    if args.tail_seconds <= 0:
        parser.error("--tail-seconds must be positive")
    if args.output:
        output_format = args.output.suffix.lower().removeprefix(".")
        if len(args.inputs) != 1 or output_format not in {"srt", "vtt"} or args.format:
            parser.error("--output requires one input, a .srt or .vtt filename, and no --format")
    else:
        if not args.format:
            parser.error("--output-dir requires --format")
        output_format = args.format
        try:
            args.output_dir.mkdir(parents=True, exist_ok=True)
        except OSError as error:
            print(f"error: {error}", file=sys.stderr)
            return 1

    failed = False
    for source in args.inputs:
        target = args.output or args.output_dir / f"{source.name}.{output_format}"
        try:
            if source.suffix.lower() not in {".md", ".txt"}:
                raise ValueError("input filename must end in .md or .txt")
            result = convert(source.read_text(encoding="utf-8-sig"), output_format, args.tail_seconds)
            write_new_subtitle(target, result.subtitle)
        except (OSError, ValueError) as error:
            print(f"{source} -> {target}: error: {error}", file=sys.stderr)
            failed = True
            continue

        print(
            f"{target}: validated {result.entries} cues, "
            f"{result.shared_starts} same-start groups; "
            f"estimated final end {format_clock(result.final_end)}"
        )
    return int(failed)


def write_new_subtitle(target: Path, subtitle: str) -> None:
    handle = target.open("x", encoding="utf-8", newline="\n")
    try:
        with handle:
            handle.write(subtitle)
    except OSError:
        target.unlink(missing_ok=True)
        raise


if __name__ == "__main__":
    sys.exit(main())
