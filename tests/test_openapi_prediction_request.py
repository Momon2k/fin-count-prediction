import unittest

from app.main import app


class OpenAPIPredictionRequestSchemaTests(unittest.TestCase):
    def test_prediction_request_required_fields(self):
        schema = app.openapi()
        components = schema.get("components", {}).get("schemas", {})
        req = components.get("PredictionRequest", {})

        required = set(req.get("required") or [])
        properties = set((req.get("properties") or {}).keys())

        self.assertEqual(required, {"species", "province", "city", "barangay", "dateFrom", "dateTo"})
        self.assertNotIn("fingerlings", required)
        self.assertNotIn("fingerlings", properties)

