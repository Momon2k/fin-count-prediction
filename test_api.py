import requests
import json

url = "http://localhost:8000/api/v1/predict"
payload = {
    "city": "0",
    "dateFrom": "2024-01-01",
    "dateTo": "2024-01-31",
    "province": "0",
    "barangay": "0",
    "fingerlings": 5000,
    "species": "0"
}

response = requests.post(url, json=payload)
print(f"Status Code: {response.status_code}")
print(f"Response: {json.dumps(response.json(), indent=2)}")
