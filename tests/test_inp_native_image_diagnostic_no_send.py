"""INP publisher photo diagnosis only: fail closed; never authorize CDNs."""
import unittest

from rasd_inp_image_diagnostic_no_send import photo_classification


def row(visible=True, loaded=False, origin="first_party"):
    return {"visible":visible,"loaded":loaded,"origin":origin}


class OriginalInstituteNativeImageTests(unittest.TestCase):
    def test_late_native_publisher_photo_can_finish_without_bypass(self):
        result=photo_classification([
            [row()], [row()], [row(loaded=True)]])
        self.assertEqual(result,"ORIGINAL_IMAGE_LOADED_AFTER_BOUNDED_WAIT")

    def test_unloaded_native_photo_remains_hold(self):
        self.assertEqual(photo_classification(
            [[row()], [row()], [row()]]),
            "FIRST_PARTY_ORIGINAL_ARTICLE_IMAGE_STILL_UNLOADED")

    def test_external_photo_never_auto_authorized(self):
        self.assertEqual(photo_classification(
            [[row(origin="external")], [row(origin="external")]]),
            "EXTERNAL_ARTICLE_IMAGE_BLOCKED_BY_ORIGIN_POLICY")

    def test_invalid_state_fails_closed(self):
        for values in (None, [], [{}], [[{"visible":True}]], [["invalid"]]):
            with self.subTest(values=values):
                self.assertEqual(photo_classification(values),
                                 "IMAGE_STATES_INVALID_HOLD")

    def test_no_image_visible_can_verify_empty_visible_window(self):
        self.assertEqual(photo_classification(
            [[row(visible=False)],[row(visible=False,loaded=True)]]),
            "ORIGINAL_VISIBLE_IMAGES_LOADED")


if __name__=="__main__":
    unittest.main()
