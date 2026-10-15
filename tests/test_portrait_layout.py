"""Regression checks: uploaded portrait must not be cropped by UI frames."""
from pathlib import Path
import re
import unittest

CSS = (Path(__file__).resolve().parents[1] / "static" / "styles.css").read_text()


def rules(selector):
    return [body for matched, body in re.findall(r"([^{}]+)\{([^{}]*)\}", CSS)
            if selector in [s.strip() for s in matched.split(",")]]


class PortraitLayoutTests(unittest.TestCase):
    def test_sidebar_portrait_shows_all_image_pixels(self):
        self.assertTrue(any("object-fit:contain" in rule for rule in rules(".character-thumb")))
        self.assertTrue(any("aspect-ratio:3/4" in rule and "height:auto" in rule
                            for rule in rules(".character-emblem")))

    def test_character_sheet_portrait_shows_complete_image(self):
        self.assertTrue(any("object-fit:contain" in rule for rule in rules(".codex-portrait img")))
        self.assertTrue(any("aspect-ratio:3/4" in rule and "height:auto" in rule
                            for rule in rules(".codex-portrait")))

    def test_responsive_layout_does_not_reintroduce_crop(self):
        self.assertTrue(any("height:auto" in rule for rule in rules(".codex-portrait")
                            if "width:min(300px,76vw)" in rule))


if __name__ == "__main__":
    unittest.main()
