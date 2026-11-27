"""Parse transcript exports, render subtitles, and verify the result."""

from collections import Counter
from dataclasses import dataclass
from html import escape, unescape
import re

SOURCE_HEADER = re.compile(
    r"(?P<speaker>[^\n]+?)\((?P<start>[0-9]{2,}:[0-5][0-9]:[0-5][0-9])\):[ \n]"
)
CLOCK = r"([0-9]{2,}):([0-5][0-9]):([0-5][0-9])"
VOICE = re.compile(r"<v ([^<>\n]+)>([\s\S]+)</v>")


@dataclass(frozen=True)
class Entry:
    speaker: str
    start: int
    text: str


@dataclass(frozen=True)
class Conversion:
    subtitle: str
    entries: int
    shared_starts: int
    final_end: int


def parse_transcript(source: str) -> list[Entry]:
    source = source.removeprefix("\ufeff").replace("\r\n", "\n").replace("\r", "\n")
    entries = []
    for index, block in enumerate(source.rstrip("\n").split("\n\n"), 1):
        header = SOURCE_HEADER.match(block)
        if not header:
            raise ValueError(f"source block {index}: expected speaker(HH:MM:SS): and text")
        speaker = header["speaker"]
        body = block[header.end():]
        if not speaker.strip() or "\x00" in block or any(
            not line.strip() for line in body.split("\n")
        ):
            raise ValueError(f"source block {index}: empty speaker or invalid subtitle text")
        if any(SOURCE_HEADER.match(line) for line in body.split("\n")):
            raise ValueError(f"source block {index}: missing blank line before a speaker header")
        start = parse_clock(header["start"])
        if entries and start < entries[-1].start:
            raise ValueError(f"source block {index}: start time goes backwards")
        entries.append(Entry(speaker, start, body))
    return entries


def parse_clock(value: str) -> int:
    hours, minutes, seconds = map(int, value.split(":"))
    return hours * 3600 + minutes * 60 + seconds


def format_clock(seconds: int) -> str:
    hours, remaining = divmod(seconds, 3600)
    minutes, second = divmod(remaining, 60)
    return f"{hours:02d}:{minutes:02d}:{second:02d}"


def render(entries: list[Entry], ends: dict[int, int], output_format: str) -> str:
    webvtt = output_format == "vtt"
    blocks = ["WEBVTT"] if webvtt else []
    fraction = ".000" if webvtt else ",000"
    for number, entry in enumerate(entries, 1):
        start = format_clock(entry.start) + fraction
        end = format_clock(ends[entry.start]) + fraction
        timing = f"{start} --> {end}"
        if webvtt:
            speaker = escape(entry.speaker, quote=False)
            body = escape(entry.text, quote=False)
            blocks.append(f"{timing}\n<v {speaker}>{body}</v>")
        else:
            blocks.append(f"{number}\n{timing}\n{entry.speaker}：{entry.text}")
    return "\n\n".join(blocks) + "\n"


def validate(
    subtitle: str, entries: list[Entry], ends: dict[int, int], output_format: str
) -> None:
    webvtt = output_format == "vtt"
    blocks = subtitle.removesuffix("\n").split("\n\n")
    if webvtt and blocks.pop(0) != "WEBVTT":
        raise ValueError("invalid WebVTT header")
    if len(blocks) != len(entries):
        raise ValueError(f"expected {len(entries)} subtitle cues, found {len(blocks)}")

    fraction = r"\.000" if webvtt else ",000"
    timing_pattern = re.compile(f"{CLOCK}{fraction} --> {CLOCK}{fraction}")
    for number, (block, entry) in enumerate(zip(blocks, entries), 1):
        if not webvtt:
            index, _, block = block.partition("\n")
            if index != str(number):
                raise ValueError(f"cue {number}: invalid SRT index")
        timing, _, body = block.partition("\n")
        match = timing_pattern.fullmatch(timing)
        if not match:
            raise ValueError(f"cue {number}: invalid timestamp syntax")
        start = parse_clock(":".join(match.groups()[:3]))
        end = parse_clock(":".join(match.groups()[3:]))
        if start != entry.start or end != ends[entry.start] or end <= start:
            raise ValueError(f"cue {number}: timing does not match the transcript")
        if webvtt:
            voice = VOICE.fullmatch(body)
            if (
                not voice or re.search(r"[<>]|&(?!amp;|lt;|gt;)", "".join(voice.groups()))
                or tuple(map(unescape, voice.groups())) != (entry.speaker, entry.text)
            ):
                raise ValueError(f"cue {number}: invalid WebVTT voice or changed text")
        elif body != f"{entry.speaker}：{entry.text}":
            raise ValueError(f"cue {number}: SRT speaker or text changed")


def convert(source: str, output_format: str, tail_seconds: int = 5) -> Conversion:
    if output_format not in {"srt", "vtt"} or tail_seconds <= 0:
        raise ValueError("expected srt or vtt and a positive tail duration")
    entries = parse_transcript(source)
    counts = Counter(entry.start for entry in entries)
    starts = list(counts)
    final_end = starts[-1] + tail_seconds
    ends = dict(zip(starts, starts[1:] + [final_end]))
    subtitle = render(entries, ends, output_format)
    validate(subtitle, entries, ends, output_format)
    return Conversion(subtitle, len(entries), sum(n > 1 for n in counts.values()), final_end)
