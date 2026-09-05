import importlib.util
import os
import subprocess
import unittest
from pathlib import Path
from unittest.mock import patch


SCRIPT = Path(__file__).resolve().parents[1] / "publish.py"
SPEC = importlib.util.spec_from_file_location("publish", SCRIPT)
assert SPEC is not None and SPEC.loader is not None
publish = importlib.util.module_from_spec(SPEC)
SPEC.loader.exec_module(publish)


class PublishTests(unittest.TestCase):
    def test_real_publish_skips_existing_version(self) -> None:
        with (
            patch.dict(
                os.environ,
                {"GITHUB_EVENT_NAME": "push", "RELEASE_MODE": "real"},
                clear=False,
            ),
            patch.object(publish, "package_identity", return_value=("demo", "1.2.3")),
            patch.object(publish, "registry_version_available", return_value=True),
            patch.object(publish.subprocess, "run") as run,
        ):
            publish.main()

        run.assert_not_called()

    def test_real_publish_recovers_when_upload_is_already_visible(self) -> None:
        with (
            patch.dict(
                os.environ,
                {"GITHUB_EVENT_NAME": "push", "RELEASE_MODE": "real"},
                clear=False,
            ),
            patch.object(publish, "package_identity", return_value=("demo", "1.2.3")),
            patch.object(
                publish,
                "registry_version_available",
                side_effect=[False, True],
            ),
            patch.object(
                publish.subprocess,
                "run",
                side_effect=subprocess.CalledProcessError(1, ["cargo", "publish"]),
            ) as run,
        ):
            publish.main()

        self.assertEqual(run.call_count, 1)
