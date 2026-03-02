import unittest

from app import crud


class _FakeResult:
    def mappings(self):
        return self

    def all(self):
        return []


class _FakeDB:
    def __init__(self):
        self.last_sql = None
        self.last_params = None

    def execute(self, sql, params):
        self.last_sql = getattr(sql, "text", str(sql))
        self.last_params = params
        return _FakeResult()


class CrudMonthlyGroupsTests(unittest.TestCase):
    def test_monthly_grouping_buckets_by_actual_harvest_date(self):
        db = _FakeDB()

        crud.get_distribution_monthly_groups(
            db=db,
            date_from="2024-01-01",
            date_to="2024-12-31",
            species="Bangus",
            province="All Provinces",
            city="All Cities",
            barangay="All Barangays",
        )

        self.assertIsInstance(db.last_sql, str)
        self.assertIn("COALESCE(`actualHarvestDate`, `dateDistributed`)", db.last_sql)
        self.assertIn("YEAR(COALESCE(`actualHarvestDate`, `dateDistributed`)) AS year", db.last_sql)
        self.assertIn("MONTH(COALESCE(`actualHarvestDate`, `dateDistributed`)) AS month", db.last_sql)
        self.assertIn("COALESCE(`actualHarvestDate`, `dateDistributed`) BETWEEN :date_from AND :date_to", db.last_sql)

        self.assertEqual(
            db.last_params,
            {"date_from": "2024-01-01", "date_to": "2024-12-31", "species": "Bangus"},
        )

