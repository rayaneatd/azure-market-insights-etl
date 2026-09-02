import unittest
from unittest.mock import MagicMock
import patito as pt
from src.igdb.models import BaseIGDBSchema
from src.database.analytics import sync_table_indexes


class DummyIndexModel(BaseIGDBSchema):
    _endpoint = "/dummy"
    _conserve_history = False
    _index_at = ()

    id: int = pt.Field(unique=True)
    name: str
    slug: str | None = None
    status: int | None = None
    score: float | None = None


class DummyScd2IndexModel(BaseIGDBSchema):
    _endpoint = "/dummy_scd2"
    _conserve_history = True
    _index_at = ()

    id: int = pt.Field(unique=True)
    title: str


class TestIndexManagement(unittest.TestCase):

    def test_empty_index_at(self):
        """Verifies that an empty _index_at returns an empty index list."""
        DummyIndexModel._index_at = ()
        self.assertEqual(DummyIndexModel.get_indexes(), [])

    def test_single_string_index(self):
        """Verifies that a single string is normalized to a single-column index tuple."""
        DummyIndexModel._index_at = "name"
        self.assertEqual(DummyIndexModel.get_indexes(), [("name",)])

    def test_multiple_single_column_indexes(self):
        """Verifies that multiple string entries create distinct single-column index specs."""
        DummyIndexModel._index_at = ("name", "slug")
        self.assertEqual(DummyIndexModel.get_indexes(), [("name",), ("slug",)])

    def test_composite_and_mixed_indexes(self):
        """Verifies support for composite tuples mixed with single column indexes."""
        DummyIndexModel._index_at = ("name", ("status", "score"), "slug")
        self.assertEqual(
            DummyIndexModel.get_indexes(),
            [("name",), ("status", "score"), ("slug",)]
        )

    def test_technical_columns_allowed(self):
        """Verifies that technical columns (_valid_from, _ingested_at, etc.) can be indexed."""
        DummyScd2IndexModel._index_at = ("_valid_from", "title")
        self.assertEqual(
            DummyScd2IndexModel.get_indexes(),
            [("_valid_from",), ("title",)]
        )

    def test_invalid_column_name_raises_value_error(self):
        """Verifies that referencing a non-existent column raises ValueError."""
        DummyIndexModel._index_at = ("non_existent_column",)
        with self.assertRaises(ValueError) as ctx:
            DummyIndexModel.get_indexes()
        self.assertIn("non_existent_column", str(ctx.exception))

    def test_invalid_index_element_type_raises_value_error(self):
        """Verifies that invalid types within _index_at raise ValueError."""
        DummyIndexModel._index_at = (123,)  # type: ignore[assignment]
        with self.assertRaises(ValueError):
            DummyIndexModel.get_indexes()

    def test_index_name_formatting_and_length_limit(self):
        """Verifies index name determinism and PostgreSQL 63-byte NAMEDATALEN limit."""
        cols = ("name",)
        idx_name = DummyIndexModel.get_index_name(cols)
        self.assertEqual(idx_name, "idx_dummy_name")
        self.assertLessEqual(len(idx_name), 63)

        # Very long column combination exceeding 63 characters
        long_cols = (
            "very_long_column_name_that_exceeds_postgres_limit_one",
            "very_long_column_name_that_exceeds_postgres_limit_two"
        )
        long_name = DummyIndexModel.get_index_name(long_cols)
        self.assertLessEqual(len(long_name), 63)
        self.assertTrue(long_name.startswith("idx_dummy_"))
        # Verify deterministic output
        self.assertEqual(long_name, DummyIndexModel.get_index_name(long_cols))

    def test_build_pg_query_includes_multiple_indexes(self):
        """Verifies that build_pg_query generates CREATE INDEX for each index spec."""
        DummyIndexModel._index_at = ("name", ("status", "score"))
        query = DummyIndexModel.build_pg_query()

        self.assertIn('CREATE INDEX IF NOT EXISTS idx_dummy_name ON dummy ("name");', query)
        self.assertIn('CREATE INDEX IF NOT EXISTS idx_dummy_status_score ON dummy ("status", "score");', query)

    def test_sync_table_indexes_creates_and_drops_correctly(self):
        """
        Verifies that sync_table_indexes compares existing DB indexes against model specs,
        dropping obsolete indexes and creating missing ones while preserving constraints.
        """
        DummyIndexModel._index_at = ("name", "slug")

        mock_pool = MagicMock()
        existing_in_db = [("idx_dummy_name",), ("idx_dummy_old_col",)]

        with unittest.mock.patch("src.database.analytics.execute_sql_from_string") as mock_exec:
            mock_exec.side_effect = [
                existing_in_db,  # Result of SELECT query
                None,            # DROP INDEX idx_dummy_old_col
                None,            # CREATE INDEX idx_dummy_slug
            ]

            sync_table_indexes(mock_pool, DummyIndexModel)

            calls = mock_exec.call_args_list
            self.assertEqual(len(calls), 3)

            # 1. Query existing
            select_call = calls[0]
            self.assertIn("SELECT i.relname AS index_name", select_call.kwargs["query"])

            # 2. DROP obsolete
            drop_call = calls[1]
            self.assertEqual(
                drop_call.kwargs["query"],
                'DROP INDEX IF EXISTS "public"."idx_dummy_old_col";'
            )

            # 3. CREATE missing
            create_call = calls[2]
            self.assertEqual(
                create_call.kwargs["query"],
                'CREATE INDEX IF NOT EXISTS idx_dummy_slug ON "public"."dummy" ("slug");'
            )


if __name__ == "__main__":
    unittest.main()
