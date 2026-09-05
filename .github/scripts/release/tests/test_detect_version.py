import importlib.util
import unittest
from pathlib import Path


SCRIPT = Path(__file__).resolve().parents[1] / "detect_version.py"
SPEC = importlib.util.spec_from_file_location("detect_version", SCRIPT)
assert SPEC is not None and SPEC.loader is not None
detect_version = importlib.util.module_from_spec(SPEC)
SPEC.loader.exec_module(detect_version)


class ReadVersionTests(unittest.TestCase):
    def test_reads_manifest_version(self) -> None:
        self.assertEqual(
            detect_version.read_version("""
                [package]
                name = "example"
                version = "0.5.0"
            """),
            "0.5.0",
        )

    def test_reads_workspace_inherited_version(self) -> None:
        self.assertEqual(
            detect_version.read_version("""
                [package]
                name = "example"
                version.workspace = true

                [workspace.package]
                version = "0.6.0"
            """),
            "0.6.0",
        )

    def test_rejects_missing_workspace_version(self) -> None:
        with self.assertRaisesRegex(RuntimeError, "usable"):
            detect_version.read_version("""
                [package]
                name = "example"
                version.workspace = true
            """)


if __name__ == "__main__":
    unittest.main()
