"""Offline visual geometry guard for the original publisher headline."""
import unittest
from capture_public import headline_visible_in_viewport


class OriginalPublisherHeadlineFraming(unittest.TestCase):
    def test_actual_hapi_original_headline_after_scroll_is_inside_screenshot(self):
        self.assertTrue(headline_visible_in_viewport(
            {"x":395,"y":119,"width":770,"height":75},
            {"width":1200,"height":900}))

    def test_off_screen_or_masthead_only_or_tiny_headline_rejected(self):
        viewport={"width":1200,"height":900}
        for box in [
            None, {},
            {"x":395,"y":565,"width":770,"height":75}, # original ad-heavy screen
            {"x":395,"y":-50,"width":770,"height":75},
            {"x":0,"y":120,"width":30,"height":75},
            {"x":600,"y":120,"width":800,"height":75},
            {"x":395,"y":120,"width":770,"height":0},
        ]:
            with self.subTest(box=box):
                self.assertFalse(headline_visible_in_viewport(box,viewport))
        self.assertFalse(headline_visible_in_viewport(
            {"x":10,"y":120,"width":850,"height":75},None))


if __name__=="__main__":
    unittest.main()
