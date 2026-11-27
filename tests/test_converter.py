from pathlib import Path
from tempfile import TemporaryDirectory
import unittest
from unittest.mock import patch

from tencent_meeting_converter.__main__ import main
from tencent_meeting_converter.core import convert, parse_transcript, validate

MD = (
    "主持人(01:00:03):\n第一行 & <文字>\n第二行\n\n"
    "来宾(01:00:03):\n同秒发言\n\n"
    "主持人(01:00:07):\n末段"
)
TXT = MD.replace("):\n", "): ")


class ConverterTest(unittest.TestCase):
    def test_layouts_produce_identical_outputs(self):
        for fmt in ("srt", "vtt"):
            with self.subTest(fmt=fmt):
                self.assertEqual(convert(MD, fmt), convert("\ufeff" + TXT.replace("\n", "\r\n"), fmt))

    def test_srt_retains_lines_and_same_start(self):
        result = convert(MD, "srt")
        self.assertEqual((result.entries, result.shared_starts, result.final_end), (3, 1, 3612))
        self.assertEqual(result.subtitle.count("01:00:03,000 --> 01:00:07,000"), 2)
        self.assertIn("主持人：第一行 & <文字>\n第二行", result.subtitle)

    def test_vtt_escapes_source_and_supports_custom_tail(self):
        result = convert(TXT, "vtt", 9)
        self.assertIn("<v 主持人>第一行 &amp; &lt;文字&gt;\n第二行</v>", result.subtitle)
        self.assertIn("01:00:07.000 --> 01:00:16.000", result.subtitle)

    def test_reject_invalid_input(self):
        for source in ("title", "甲(00:00:01): ", MD.replace("01:00:07", "00:00:07")):
            with self.subTest(source=source), self.assertRaises(ValueError):
                convert(source, "vtt")
        with self.assertRaisesRegex(ValueError, "missing blank"):
            convert(TXT.replace("\n\n", "\n", 1), "srt")

    def test_validation_rejects_changed_cues(self):
        entries = parse_transcript(TXT)
        ends = {3603: 3607, 3607: 3612}
        for fmt in ("srt", "vtt"):
            original = convert(TXT, fmt).subtitle
            for replacement in (
                original.replace("末段", "改动"),
                original.replace("01:00:12", "01:00:07"),
                original.replace("01:00:03", "01:00:02"),
                original.split("\n\n")[-1],
            ):
                with self.subTest(fmt=fmt, replacement=replacement), self.assertRaises(ValueError):
                    validate(replacement, entries, ends, fmt)

    def test_batch_continues_and_never_overwrites(self):
        with TemporaryDirectory() as directory:
            root = Path(directory)
            md, txt, broken = (root / name for name in ("meeting.md", "meeting.txt", "broken.md"))
            md.write_text(MD, encoding="utf-8")
            txt.write_text(TXT, encoding="utf-8")
            broken.write_text("broken", encoding="utf-8")
            output = root / "subtitles"
            output.mkdir()
            existing = output / "meeting.md.vtt"
            existing.write_text("keep", encoding="utf-8")
            with patch("sys.stdout"), patch("sys.stderr"):
                self.assertEqual(main([str(md), str(broken), str(txt), "-d", str(output), "--format", "vtt"]), 1)
            self.assertEqual(existing.read_text(), "keep")
            self.assertFalse((output / "broken.md.vtt").exists())
            self.assertEqual((output / "meeting.txt.vtt").read_text(), convert(TXT, "vtt").subtitle)
