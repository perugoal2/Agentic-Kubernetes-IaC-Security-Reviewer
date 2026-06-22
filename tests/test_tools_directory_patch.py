import shutil
import tempfile
import unittest
from pathlib import Path
from unittest.mock import patch

import tools


class DirectoryPatchTests(unittest.TestCase):
    def setUp(self):
        self.temp_dir = tempfile.TemporaryDirectory()
        self.addCleanup(self.temp_dir.cleanup)
        self.root = Path(self.temp_dir.name)
        self.original_patch_dir = tools.PATCH_DIR
        tools.PATCH_DIR = str(self.root / "patches")

    def tearDown(self):
        tools.PATCH_DIR = self.original_patch_dir

    def test_propose_patch_preserves_relative_path_with_root(self):
        review_root = self.root / "manifests"
        source_file = review_root / "apps" / "deployment.yaml"
        source_file.parent.mkdir(parents=True)
        source_file.write_text("kind: Deployment\n")

        result = tools.propose_patch(
            str(source_file),
            "kind: Deployment\nmetadata:\n  name: fixed\n",
            root_path=str(review_root),
        )

        patched_path = Path(result["patched_path"])
        patched_root = Path(result["patched_root"])

        self.assertEqual(patched_root, Path(tools.PATCH_DIR) / review_root.name)
        self.assertEqual(patched_path, patched_root / "apps" / "deployment.yaml")
        self.assertTrue(patched_path.exists())

    def test_validate_patch_accepts_directory_roots(self):
        original_root = self.root / "original"
        patched_root = self.root / "patched"
        original_root.mkdir()
        patched_root.mkdir()

        before_checkov = [{"id": "CKV_1", "resource": "deployment"}, {"id": "CKV_2", "resource": "service"}]
        after_checkov = [{"id": "CKV_2", "resource": "service"}, {"id": "CKV_3", "resource": "ingress"}]
        before_trivy = [{"id": "KSV_1", "resource": "deployment"}]
        after_trivy = [{"id": "KSV_1", "resource": "deployment"}, {"id": "KSV_2", "resource": "pod"}]

        with patch.object(tools, "run_checkov", side_effect=[{"findings": before_checkov}, {"findings": after_checkov}]), patch.object(
            tools, "run_trivy", side_effect=[{"findings": before_trivy}, {"findings": after_trivy}]
        ):
            result = tools.validate_patch(str(original_root), str(patched_root))

        self.assertEqual(set(result["resolved"]), {("CKV_1", "deployment")})
        self.assertEqual(set(result["remaining"]), {("CKV_2", "service"), ("CKV_3", "ingress"), ("KSV_1", "deployment"), ("KSV_2", "pod")})
        self.assertEqual(set(result["new"]), {("CKV_3", "ingress"), ("KSV_2", "pod")})
        self.assertFalse(result["success"])


if __name__ == "__main__":
    unittest.main()