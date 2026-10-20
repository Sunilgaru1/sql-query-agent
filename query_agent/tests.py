from django.test import SimpleTestCase

from query_agent.exceptions import UnsafeSQLError
from query_agent.services import TextToSQLAgent


class SecurityGatewayTests(SimpleTestCase):
    def setUp(self) -> None:
        self.agent = TextToSQLAgent()

    def test_allows_select(self) -> None:
        self.agent.validate_sql("SELECT id, name FROM employees WHERE department = 'IT'")

    def test_blocks_drop(self) -> None:
        with self.assertRaises(UnsafeSQLError):
            self.agent.validate_sql("DROP TABLE employees")

    def test_blocks_delete(self) -> None:
        with self.assertRaises(UnsafeSQLError):
            self.agent.validate_sql("DELETE FROM employees")

    def test_blocks_update(self) -> None:
        with self.assertRaises(UnsafeSQLError):
            self.agent.validate_sql("UPDATE employees SET salary = 0")

    def test_blocks_insert(self) -> None:
        with self.assertRaises(UnsafeSQLError):
            self.agent.validate_sql("INSERT INTO employees (name) VALUES ('x')")

    def test_blocks_multiple_statements(self) -> None:
        with self.assertRaises(UnsafeSQLError):
            self.agent.validate_sql("SELECT 1; DROP TABLE employees")

    def test_blocks_select_into_outfile(self) -> None:
        with self.assertRaises(UnsafeSQLError):
            self.agent.validate_sql("SELECT * FROM employees INTO OUTFILE '/tmp/x.csv'")
