import tempfile
import unittest
from pathlib import Path
from unittest.mock import patch

import backend.services.api_generator as api_generator


class TestApiStorage(unittest.TestCase):
    def test_save_generated_route_writes_python_file(self):
        with tempfile.TemporaryDirectory() as tmpdir:
            target_dir = Path(tmpdir)
            route_code = "from fastapi import APIRouter\nrouter = APIRouter()\n"

            with patch.object(api_generator, "GENERATED_APIS_DIR", target_dir):
                saved = api_generator.save_generated_route("Show customer totals", route_code)

            saved_path = Path(saved)
            self.assertTrue(saved_path.exists())
            self.assertIn("query_", saved_path.name)
            self.assertIn("APIRouter", saved_path.read_text(encoding="utf-8"))

    def test_list_generated_api_files_returns_metadata(self):
        with tempfile.TemporaryDirectory() as tmpdir:
            target_dir = Path(tmpdir)
            (target_dir / "customers.py").write_text("router = object()\n", encoding="utf-8")
            (target_dir / "query_20260101_120000_customer_totals.py").write_text(
                "router = object()\n",
                encoding="utf-8",
            )

            with patch.object(api_generator, "GENERATED_APIS_DIR", target_dir):
                files = api_generator.list_generated_api_files()

            self.assertEqual(len(files), 2)
            self.assertEqual(files[0]["kind"], "crud_router")
            self.assertEqual(files[1]["kind"], "query_route")


if __name__ == "__main__":
    unittest.main()
