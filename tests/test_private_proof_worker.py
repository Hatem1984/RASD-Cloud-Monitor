"""Manual storage authorization is checked before R2 or publisher activity."""
import unittest

from private_proof_worker import (
    checked_configuration, run, EXPECTED_REF, ONE_RUN_CONFIRMATION,
    OWNER_UPLOAD_APPROVAL,
)

ENV = {
    "GITHUB_EVENT_NAME": "workflow_dispatch",
    "GITHUB_REF": "refs/heads/main",
    "GITHUB_REPOSITORY": "Hatem1984/RASD-Cloud-Monitor",
    "GITHUB_WORKFLOW_REF": EXPECTED_REF,
    "GITHUB_RUN_ATTEMPT": "1",
    "GITHUB_RUN_ID": "12341234",
    "GITHUB_ACTOR": "Hatem1984",
    "RASD_ARCHIVE_RUN_CONFIRMATION": ONE_RUN_CONFIRMATION,
    "RASD_PRIVATE_ARCHIVE_ENABLED": OWNER_UPLOAD_APPROVAL,
    "RASD_R2_ACCOUNT_ID": "a" * 32,
    "RASD_R2_BUCKET": "rasd-private-evidence",
    "RASD_R2_ACCESS_KEY_ID": "fake-id-for-test",
    "RASD_R2_SECRET_ACCESS_KEY": "fake-secret-for-test",
}


class PrivateStorageApprovalTests(unittest.TestCase):
    def test_verified_owner_environment_builds_r2_endpoint(self):
        settings = checked_configuration(dict(ENV))
        self.assertEqual(settings["endpoint_url"],
                         "https://" + "a" * 32 + ".r2.cloudflarestorage.com")
        self.assertEqual(settings["bucket"], "rasd-private-evidence")

    def test_unapproved_and_replayed_runs_never_touch_storage_or_publishers(self):
        for override in [
            {"GITHUB_EVENT_NAME": "schedule"},
            {"GITHUB_REF": "refs/heads/develop"},
            {"GITHUB_RUN_ATTEMPT": "2"},
            {"GITHUB_ACTOR": "someone-else"},
            {"RASD_ARCHIVE_RUN_CONFIRMATION": ""},
            {"RASD_PRIVATE_ARCHIVE_ENABLED": ""},
            {"GITHUB_WORKFLOW_REF": "wrong-workflow"},
        ]:
            with self.subTest(override=override):
                env = {**ENV, **override}
                def fail_on_storage(**kwargs):
                    self.fail("must never instantiate storage before approval")
                def fail_on_publish(*args, **kwargs):
                    self.fail("must never scan sources before approval")
                with self.assertRaises(RuntimeError):
                    run(environ=env, s3_factory=fail_on_storage,
                        generator=fail_on_publish)

    def test_missing_bucket_or_key_never_contacts_r2(self):
        for key in ("RASD_R2_BUCKET", "RASD_R2_ACCESS_KEY_ID",
                    "RASD_R2_SECRET_ACCESS_KEY", "RASD_R2_ACCOUNT_ID"):
            with self.subTest(key=key):
                env = {**ENV, key: ""}
                with self.assertRaises(RuntimeError):
                    run(environ=env,
                        s3_factory=lambda **kw: self.fail("network forbidden"))

    def test_approved_storage_mock_produces_no_email_or_schedule(self):
        params = {}
        def factory(**kwargs):
            params.update(kwargs)
            return object()
        def generator(path, output, *, archive_writer):
            self.assertEqual(archive_writer.bucket, "rasd-private-evidence")
            return {"status": "HOLD", "archive_status": "NOT_ATTEMPTED",
                    "articles": 1, "screenshots_verified": 0,
                    "screenshots_missing": 1, "coverage": "HEALTHY",
                    "word_created": False}
        result = run(environ=dict(ENV), s3_factory=factory, generator=generator)
        self.assertEqual(result["status"], "HOLD")
        self.assertIn("endpoint_url", params)
        self.assertNotIn("email_sent", result)


if __name__ == "__main__":
    unittest.main()
