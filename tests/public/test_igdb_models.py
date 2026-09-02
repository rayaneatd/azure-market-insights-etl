import unittest
from src.igdb.models import GameSchema, GenreSchema, BaseIGDBSchema


class TestIGDBModels(unittest.TestCase):

    def test_apicalypse_query_builder_contains_declared_fields(self):
        """
        Verifies that the Apicalypse query builder correctly formats requested IGDB fields
        and respects limit/watermark conditions.
        """
        query = GameSchema.build_query(
            last_update_value=1700000000,
            limit=500,
            offset=0
        )

        self.assertTrue(query.startswith("fields "))
        self.assertIn("name", query)
        self.assertIn("rating", query)
        self.assertIn("where updated_at >= 1700000000;", query)
        self.assertIn("limit 500;", query)

    def test_table_name_resolution_scd1_vs_scd2(self):
        """
        Ensures table name resolution appends '_scd2' suffix if _conserve_history is enabled.
        """
        self.assertEqual(GameSchema.get_table_name(), "games_scd2")
        self.assertEqual(GenreSchema.get_table_name(), "genres")

    def test_schema_snapshot_generation(self):
        """
        Verifies snapshot dictionary generation of table model fields.
        """
        snapshot = GameSchema.get_columns_snapshot(format="dict")
        self.assertIsInstance(snapshot, dict)
        self.assertIn("name", snapshot)
        self.assertIn("rating", snapshot)


if __name__ == "__main__":
    unittest.main()
