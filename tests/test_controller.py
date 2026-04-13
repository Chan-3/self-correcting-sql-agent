import unittest
from unittest.mock import patch

import backend.core.controller as controller


class TestController(unittest.TestCase):
    @patch("backend.core.controller.execute_query")
    @patch("backend.core.controller._correction_loop")
    @patch("backend.core.controller.validate_sql")
    @patch("backend.core.controller.generate_sql")
    @patch("backend.core.controller.get_schema")
    def test_no_double_execute_after_validation_correction(
        self,
        mock_get_schema,
        mock_generate_sql,
        mock_validate_sql,
        mock_correction_loop,
        mock_execute_query,
    ):
        mock_get_schema.return_value = {"customers": {"columns": [], "foreign_keys": []}}
        mock_generate_sql.return_value = "SELECT bad_sql"
        mock_validate_sql.return_value = {
            "valid": False,
            "errors": ["syntax issue"],
            "warnings": [],
        }

        def _mark_success(user_request, sql, error, schema, result, intent_policy, confirmed, execute):
            result.success = True
            result.sql = "SELECT 1;"
            result.rows = [{"x": 1}]
            result.affected_rows = 1
            return "SELECT 1;"

        mock_correction_loop.side_effect = _mark_success

        result = controller.run_query("test request")

        self.assertTrue(result.success)
        self.assertEqual(result.sql, "SELECT 1;")
        mock_execute_query.assert_not_called()

    @patch("backend.core.controller.execute_query")
    @patch("backend.core.controller.save_generated_route")
    @patch("backend.core.controller.generate_api_route")
    @patch("backend.core.controller.validate_sql")
    @patch("backend.core.controller.generate_sql")
    @patch("backend.core.controller.get_schema")
    def test_execute_called_once_on_clean_path(
        self,
        mock_get_schema,
        mock_generate_sql,
        mock_validate_sql,
        mock_generate_api_route,
        mock_save_generated_route,
        mock_execute_query,
    ):
        mock_get_schema.return_value = {"customers": {"columns": [], "foreign_keys": []}}
        mock_generate_sql.return_value = "SELECT c.id FROM customers c;"
        mock_validate_sql.return_value = {"valid": True, "errors": [], "warnings": []}
        mock_generate_api_route.return_value = "from fastapi import APIRouter\nrouter = APIRouter()\n"
        mock_save_generated_route.return_value = "generated/apis/query_test.py"
        mock_execute_query.return_value = {
            "success": True,
            "rows": [{"id": 1}],
            "affected": 1,
            "error": None,
        }

        result = controller.run_query("list customers")

        self.assertTrue(result.success)
        self.assertEqual(result.affected_rows, 1)
        mock_execute_query.assert_called_once()
        mock_generate_api_route.assert_not_called()
        mock_save_generated_route.assert_not_called()

    @patch("backend.core.controller.execute_query")
    @patch("backend.core.controller.save_generated_route")
    @patch("backend.core.controller.generate_api_route")
    @patch("backend.core.controller.validate_sql")
    @patch("backend.core.controller.generate_sql")
    @patch("backend.core.controller.get_schema")
    def test_generate_api_saves_route_file(
        self,
        mock_get_schema,
        mock_generate_sql,
        mock_validate_sql,
        mock_generate_api_route,
        mock_save_generated_route,
        mock_execute_query,
    ):
        mock_get_schema.return_value = {"customers": {"columns": [], "foreign_keys": []}}
        mock_generate_sql.return_value = "SELECT c.id FROM customers c;"
        mock_validate_sql.return_value = {"valid": True, "errors": [], "warnings": []}
        mock_execute_query.return_value = {
            "success": True,
            "rows": [{"id": 1}],
            "affected": 1,
            "error": None,
        }
        mock_generate_api_route.return_value = "from fastapi import APIRouter\nrouter = APIRouter()\n"
        mock_save_generated_route.return_value = "generated/apis/query_test.py"

        result = controller.run_query("list customers", generate_api=True)

        self.assertTrue(result.success)
        self.assertEqual(result.generated_file, "generated/apis/query_test.py")
        self.assertIn("APIRouter", result.api_route)
        mock_generate_api_route.assert_called_once()
        mock_save_generated_route.assert_called_once()

    @patch("backend.core.controller.execute_query")
    @patch("backend.core.controller.generate_sql")
    @patch("backend.core.controller.get_schema")
    def test_explicit_unknown_table_fails_fast(
        self,
        mock_get_schema,
        mock_generate_sql,
        mock_execute_query,
    ):
        mock_get_schema.return_value = {
            "customers": {"columns": [], "foreign_keys": []},
            "orders": {"columns": [], "foreign_keys": []},
        }

        result = controller.run_query("show rows from employee sorted in descending order")

        self.assertFalse(result.success)
        self.assertIn("does not exist", result.error)
        mock_generate_sql.assert_not_called()
        mock_execute_query.assert_not_called()

    @patch("backend.core.controller.execute_query")
    @patch("backend.core.controller.validate_sql")
    @patch("backend.core.controller.generate_sql")
    @patch("backend.core.controller.get_schema")
    def test_dry_run_returns_preview_without_execution(
        self,
        mock_get_schema,
        mock_generate_sql,
        mock_validate_sql,
        mock_execute_query,
    ):
        mock_get_schema.return_value = {"customers": {"columns": [], "foreign_keys": []}}
        mock_generate_sql.return_value = "SELECT c.id FROM customers c;"
        mock_validate_sql.return_value = {"valid": True, "errors": [], "warnings": []}

        result = controller.run_query("list customers", execute=False)

        self.assertTrue(result.success)
        self.assertEqual(result.sql, "SELECT c.id FROM customers c;")
        self.assertEqual(result.operation_type, "read")
        self.assertEqual(result.risk_level, "low")
        self.assertFalse(result.requires_confirmation)
        mock_execute_query.assert_not_called()

    @patch("backend.core.controller.execute_query")
    @patch("backend.core.controller.validate_sql")
    @patch("backend.core.controller.generate_sql")
    @patch("backend.core.controller.get_schema")
    def test_high_risk_requires_confirmation(
        self,
        mock_get_schema,
        mock_generate_sql,
        mock_validate_sql,
        mock_execute_query,
    ):
        mock_get_schema.return_value = {"customers": {"columns": [], "foreign_keys": []}}
        mock_generate_sql.return_value = "DROP TABLE customers;"
        mock_validate_sql.return_value = {"valid": True, "errors": [], "warnings": []}

        result = controller.run_query("drop customers table", confirmed=False)

        self.assertFalse(result.success)
        self.assertIn("requires confirmation", result.error)
        self.assertEqual(result.risk_level, "critical")
        self.assertTrue(result.requires_confirmation)
        mock_execute_query.assert_not_called()

    @patch("backend.core.controller.execute_query")
    @patch("backend.core.controller.validate_sql")
    @patch("backend.core.controller.generate_sql")
    @patch("backend.core.controller.get_schema")
    def test_dangerous_intent_still_requires_confirmation_if_sql_drifts(
        self,
        mock_get_schema,
        mock_generate_sql,
        mock_validate_sql,
        mock_execute_query,
    ):
        mock_get_schema.return_value = {"orders": {"columns": [], "foreign_keys": []}}
        mock_generate_sql.return_value = "DELETE FROM orders WHERE id = 1;"
        mock_validate_sql.return_value = {"valid": True, "errors": [], "warnings": []}

        result = controller.run_query("drop table orders", confirmed=False)

        self.assertFalse(result.success)
        self.assertIn("requires confirmation", result.error)
        self.assertEqual(result.intent_risk_level, "critical")
        self.assertTrue(result.requires_confirmation)
        mock_execute_query.assert_not_called()

    @patch("backend.core.controller.execute_query")
    @patch("backend.core.controller.validate_sql")
    @patch("backend.core.controller.correct_sql")
    @patch("backend.core.controller.generate_sql")
    @patch("backend.core.controller.get_schema")
    def test_dry_run_validation_correction_does_not_execute(
        self,
        mock_get_schema,
        mock_generate_sql,
        mock_correct_sql,
        mock_validate_sql,
        mock_execute_query,
    ):
        mock_get_schema.return_value = {
            "customers": {
                "columns": [
                    {"name": "id", "key": "PRI"},
                    {"name": "email", "key": ""},
                ],
                "foreign_keys": [],
            }
        }
        mock_generate_sql.return_value = "SELECT c.bad_col FROM customers c;"
        mock_correct_sql.return_value = "SELECT c.id, c.email FROM customers c;"
        mock_validate_sql.side_effect = [
            {"valid": False, "errors": ["Column 'c.bad_col' does not exist in table 'customers'."], "warnings": []},
            {"valid": True, "errors": [], "warnings": []},
        ]

        result = controller.run_query("list customers", execute=False)

        self.assertTrue(result.success)
        self.assertEqual(result.sql, "SELECT c.id, c.email FROM customers c;")
        mock_execute_query.assert_not_called()

    def test_drop_intent_ddl_block_fails_fast_without_correction(self):
        with patch.object(
            controller,
            "get_schema",
            return_value={"orders": {"columns": [], "foreign_keys": []}},
        ), patch.object(
            controller,
            "generate_sql",
            return_value="DROP TABLE orders;",
        ), patch.object(
            controller,
            "validate_sql",
            return_value={
                "valid": False,
                "errors": ["DDL statements are blocked by default (DROP/TRUNCATE/ALTER/CREATE/RENAME)."],
                "warnings": [],
            },
        ), patch.object(controller, "_populate_operation_metadata", return_value=None), patch.object(
            controller,
            "_should_fail_fast_on_validation",
            return_value=True,
        ), patch.object(
            controller,
            "execute_query",
        ) as mock_execute_query, patch.object(
            controller,
            "_correction_loop",
        ) as mock_correction_loop:
            result = controller.run_query("drop table orders", execute=False, confirmed=False)

        self.assertFalse(result.success)
        self.assertIn("DDL statements are blocked", result.error)
        mock_correction_loop.assert_not_called()
        mock_execute_query.assert_not_called()


if __name__ == "__main__":
    unittest.main()
