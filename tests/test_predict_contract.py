import unittest
from unittest.mock import patch

from fastapi.testclient import TestClient

from app.main import app
from app import main as app_main


class PredictContractTests(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        cls.client = TestClient(app)
        def override_get_db():
            yield object()
        app.dependency_overrides[app_main.get_db] = override_get_db

    @classmethod
    def tearDownClass(cls):
        app.dependency_overrides.clear()

    def _post_predict(self, payload: dict):
        return self.client.post("/api/v1/predict", json=payload)

    def _assert_success_contract(self, body: dict):
        self.assertEqual(set(body.keys()), {"success", "predictions", "model_info", "metadata"})
        self.assertIs(body["success"], True)
        self.assertIsInstance(body["predictions"], list)
        self.assertGreater(len(body["predictions"]), 0)
        self.assertIsInstance(body["model_info"], dict)
        self.assertIsInstance(body["metadata"], dict)

        for key in [
            "species",
            "province",
            "city",
            "barangay",
            "date_from",
            "date_to",
            "prediction_count",
            "total_fingerlings",
            "request_id",
            "timestamp",
        ]:
            self.assertIn(key, body["metadata"])

        self.assertIsInstance(body["metadata"]["prediction_count"], int)
        self.assertIsInstance(body["metadata"]["total_fingerlings"], (int, float))
        self.assertNotIsInstance(body["metadata"]["total_fingerlings"], str)

        for p in body["predictions"]:
            self.assertIsInstance(p["date"], str)
            self.assertRegex(p["date"], r"^\d{4}-\d{2}-\d{2}$")
            self.assertIsInstance(p["predicted_harvest"], (int, float))
            self.assertNotIsInstance(p["predicted_harvest"], str)

            if p.get("confidence_lower") is not None:
                self.assertIsInstance(p["confidence_lower"], (int, float))
                self.assertNotIsInstance(p["confidence_lower"], str)

            if p.get("confidence_upper") is not None:
                self.assertIsInstance(p["confidence_upper"], (int, float))
                self.assertNotIsInstance(p["confidence_upper"], str)

    def test_small_date_range_returns_non_empty_predictions(self):
        payload = {
            "species": "Bangus",
            "dateFrom": "2024-01-15",
            "dateTo": "2024-01-20",
            "province": "Davao del Norte",
            "city": "Panabo City",
            "barangay": "Malaga",
        }
        rows = [
            {
                "year": 2024,
                "month": 1,
                "province": "Davao del Norte",
                "municipality": "Panabo City",
                "barangay": "Malaga",
                "total_fingerlings": 5000.0,
                "total_harvest": None,
                "harvest_count": 0,
                "distribution_count": 1,
            }
        ]
        with patch.object(app_main, "is_db_available", return_value=True), \
             patch.object(app_main.crud, "get_distribution_monthly_groups", return_value=rows), \
             patch.object(app_main.predictor, "predict_single", return_value=123.45):
            resp = self._post_predict(payload)
        self.assertEqual(resp.status_code, 200)
        body = resp.json()
        self._assert_success_contract(body)

    def test_large_date_range_returns_predictions(self):
        payload = {
            "species": "Bangus",
            "dateFrom": "2024-01-01",
            "dateTo": "2024-12-30",
            "province": "Davao del Norte",
            "city": "Panabo City",
            "barangay": "Malaga",
        }
        rows = [
            {
                "year": 2024,
                "month": 1,
                "province": "Davao del Norte",
                "municipality": "Panabo City",
                "barangay": "Malaga",
                "total_fingerlings": 5000.0,
                "total_harvest": None,
                "harvest_count": 0,
                "distribution_count": 1,
            }
        ]
        with patch.object(app_main, "is_db_available", return_value=True), \
             patch.object(app_main.crud, "get_distribution_monthly_groups", return_value=rows), \
             patch.object(app_main.predictor, "predict_single", return_value=123.45):
            resp = self._post_predict(payload)
        self.assertEqual(resp.status_code, 200)
        body = resp.json()
        self._assert_success_contract(body)

    def test_species_change_keeps_contract(self):
        base = {
            "dateFrom": "2024-01-01",
            "dateTo": "2024-03-31",
            "province": "Davao del Norte",
            "city": "Panabo City",
            "barangay": "Malaga",
        }

        rows = [
            {
                "year": 2024,
                "month": 1,
                "province": "Davao del Norte",
                "municipality": "Panabo City",
                "barangay": "Malaga",
                "total_fingerlings": 5000.0,
                "total_harvest": None,
                "harvest_count": 0,
                "distribution_count": 1,
            }
        ]
        with patch.object(app_main, "is_db_available", return_value=True), \
             patch.object(app_main.crud, "get_distribution_monthly_groups", return_value=rows), \
             patch.object(app_main.predictor, "predict_single", return_value=123.45):
            resp1 = self._post_predict({**base, "species": "Bangus"})
            resp2 = self._post_predict({**base, "species": "Red Tilapia"})
        self.assertEqual(resp1.status_code, 200)
        body1 = resp1.json()
        self._assert_success_contract(body1)
        self.assertEqual(body1["model_info"]["species"], "all")

        self.assertEqual(resp2.status_code, 200)
        body2 = resp2.json()
        self._assert_success_contract(body2)
        self.assertEqual(body2["model_info"]["species"], "all")

    def test_province_change_keeps_contract(self):
        payload1 = {
            "species": "Bangus",
            "dateFrom": "2024-01-01",
            "dateTo": "2024-03-31",
            "province": "Davao del Norte",
            "city": "Panabo City",
            "barangay": "Malaga",
        }
        payload2 = {
            "species": "Bangus",
            "dateFrom": "2024-01-01",
            "dateTo": "2024-03-31",
            "province": "Davao del Sur",
            "city": "Davao City",
            "barangay": "Buhangin",
        }

        rows = [
            {
                "year": 2024,
                "month": 1,
                "province": "Davao del Norte",
                "municipality": "Panabo City",
                "barangay": "Malaga",
                "total_fingerlings": 5000.0,
                "total_harvest": None,
                "harvest_count": 0,
                "distribution_count": 1,
            }
        ]
        with patch.object(app_main, "is_db_available", return_value=True), \
             patch.object(app_main.crud, "get_distribution_monthly_groups", return_value=rows), \
             patch.object(app_main.predictor, "predict_single", return_value=123.45):
            resp1 = self._post_predict(payload1)
            resp2 = self._post_predict(payload2)
        self.assertEqual(resp1.status_code, 200)
        self._assert_success_contract(resp1.json())

        self.assertEqual(resp2.status_code, 200)
        self._assert_success_contract(resp2.json())

    def test_no_data_scenario_returns_error_not_success(self):
        payload = {
            "species": "Bangus",
            "dateFrom": "2024-01-01",
            "dateTo": "2024-01-31",
            "province": "Davao del Norte",
            "city": "Panabo City",
            "barangay": "Malaga",
        }

        with patch.object(app_main, "is_db_available", return_value=True), \
             patch.object(app_main.crud, "get_distribution_monthly_groups", return_value=[]):
            resp = self._post_predict(payload)
        self.assertEqual(resp.status_code, 404)
        body = resp.json()
        self.assertEqual(set(body.keys()), {"success", "error", "detail"})
        self.assertIs(body["success"], False)
        self.assertIsInstance(body["error"], str)

    def test_unknown_label_returns_error(self):
        payload = {
            "species": "__unknown__",
            "dateFrom": "2024-01-01",
            "dateTo": "2024-01-31",
            "province": "Davao del Norte",
            "city": "Panabo City",
            "barangay": "Malaga",
        }

        rows = [
            {
                "year": 2024,
                "month": 1,
                "province": "Davao del Norte",
                "municipality": "Panabo City",
                "barangay": "Malaga",
                "total_fingerlings": 5000.0,
                "total_harvest": None,
                "harvest_count": 0,
                "distribution_count": 1,
            }
        ]
        with patch.object(app_main, "is_db_available", return_value=True), \
             patch.object(app_main.crud, "get_distribution_monthly_groups", return_value=rows), \
             patch.object(app_main.predictor, "predict_single", side_effect=ValueError("Unknown label for Species: __unknown__")):
            resp = self._post_predict(payload)
        self.assertEqual(resp.status_code, 400)
        body = resp.json()
        self.assertEqual(set(body.keys()), {"success", "error", "detail"})
        self.assertIs(body["success"], False)

