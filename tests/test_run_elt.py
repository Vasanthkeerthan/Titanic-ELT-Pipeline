import unittest
from contextlib import redirect_stdout
from io import StringIO

from run_elt import CHECK_NAMES, print_check_results, split_sql_statements


class SplitSqlStatementsTests(unittest.TestCase):
    def test_splits_statements_without_splitting_quoted_semicolons(self):
        script = "SELECT 'a;b'; SELECT `column;name` FROM `table`;"
        self.assertEqual(
            split_sql_statements(script),
            ["SELECT 'a;b'", "SELECT `column;name` FROM `table`"],
        )

    def test_ignores_semicolons_in_comments(self):
        script = "SELECT 1; -- comment;\nSELECT 2 /* ; */;"
        self.assertEqual(
            split_sql_statements(script),
            ["SELECT 1", "-- comment;\nSELECT 2 /* ; */"],
        )

    def test_rejects_unterminated_quotes_and_block_comments(self):
        with self.assertRaisesRegex(ValueError, "unterminated quoted"):
            split_sql_statements("SELECT 'unfinished")
        with self.assertRaisesRegex(ValueError, "unterminated block"):
            split_sql_statements("SELECT 1 /* unfinished")


class PrintCheckResultsTests(unittest.TestCase):
    def test_returns_true_when_all_expected_checks_pass(self):
        output = StringIO()
        with redirect_stdout(output):
            successful = print_check_results(
                {check_name: "PASS" for check_name in CHECK_NAMES}
            )
        self.assertTrue(successful)
        self.assertEqual(output.getvalue().count("[PASS]"), len(CHECK_NAMES))

    def test_returns_false_for_missing_or_unexpected_checks(self):
        output = StringIO()
        with redirect_stdout(output):
            successful = print_check_results(
                {"raw_count_equals_clean_count": "PASS", "unknown_check": "PASS"}
            )
        self.assertFalse(successful)
        self.assertIn("[FAIL] no_null_age (missing or invalid result)", output.getvalue())
        self.assertIn("[FAIL] Unexpected data-quality check: unknown_check", output.getvalue())


if __name__ == "__main__":
    unittest.main()
