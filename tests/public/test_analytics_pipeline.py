import unittest
import polars as pl
from src.database.analytics import (
    enforce_schema_and_types,
    deduplicate_records,
    extract_m2m_relationships,
    run_dq_checks,
)
from src.igdb.models import GameSchema, GenreSchema


class TestAnalyticsPipeline(unittest.TestCase):

    def test_enforce_schema_fills_missing_declared_fields(self):
        """
        Ensures missing optional schema fields in raw JSON are populated with nulls
        to match the target Postgres schema definition.
        """
        raw_df = pl.DataFrame({
            "id": [101, 102],
            "name": ["Elden Ring", "Cyberpunk 2077"],
            "updated_at": [1700000000, 1700000010]
        })

        enforced_df = enforce_schema_and_types(GameSchema, raw_df)

        self.assertIn("rating", enforced_df.columns)
        self.assertIn("summary", enforced_df.columns)
        self.assertEqual(enforced_df["rating"].null_count(), 2)

        # Technical audit columns
        self.assertIn("_ingested_at", enforced_df.columns)
        self.assertIn("_hash", enforced_df.columns)
        self.assertEqual(enforced_df["_hash"].null_count(), 0)

    def test_enforce_schema_drops_unexpected_fields(self):
        """
        Ensures unmapped or legacy fields present in raw data blobs are dropped
        before entering the analytics layer.
        """
        raw_df = pl.DataFrame({
            "id": [201],
            "name": ["Hades"],
            "unexpected_deprecated_field": ["legacy_val"]
        })

        enforced_df = enforce_schema_and_types(GameSchema, raw_df)

        self.assertNotIn("unexpected_deprecated_field", enforced_df.columns)
        self.assertIn("name", enforced_df.columns)

    def test_deduplicate_records_preserves_latest_record(self):
        """
        Validates deterministic deduplication on primary key ('id') keeping the most recent record
        based on 'updated_at' timestamp.
        """
        raw_df = pl.DataFrame({
            "id": [1, 1, 2],
            "name": ["Game V1", "Game V2 Updated", "Unique Game"],
            "updated_at": [1000, 2000, 1500]
        })

        deduped_df = deduplicate_records(raw_df)

        self.assertEqual(len(deduped_df), 2)
        game_1 = deduped_df.filter(pl.col("id") == 1)
        self.assertEqual(game_1["name"][0], "Game V2 Updated")

    def test_extract_m2m_relationships_for_non_scd2_model(self):
        """
        Tests extraction and explosion of array/list relationship attributes (e.g., genres, platforms)
        into separate junction table DataFrames for non-SCD2 models.
        """
        df = pl.DataFrame({
            "id": [1001],
            "name": ["Action RPG"],
            "slug": ["action-rpg"]
        })

        # GenreSchema has _conserve_history=False
        m2m_dict = extract_m2m_relationships(GenreSchema, df)
        self.assertEqual(m2m_dict, {})

    def test_run_dq_checks_fails_on_null_primary_key(self):
        """
        Ensures Data Quality checks fail if primary key 'id' contains null values.
        """
        invalid_df = pl.DataFrame({
            "id": [10, None],
            "name": ["Valid Game", "Corrupted Record"]
        })

        self.assertFalse(run_dq_checks(GameSchema, invalid_df))


if __name__ == "__main__":
    unittest.main()
