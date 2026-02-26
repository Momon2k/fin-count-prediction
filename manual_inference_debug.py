from __future__ import annotations

from datetime import datetime
from typing import Any, Dict, List

import joblib
import numpy as np
import requests


FEATURE_COLUMNS = ["Species", "Barangay", "Municipality", "Province", "Fingerlings", "Year", "Month"]


def encode_one(encoders: Dict[str, Any], col: str, raw_value: str) -> int:
    encoder = encoders.get(col)
    if encoder is None:
        raise RuntimeError(f"Missing encoder for {col}")

    try:
        encoded = int(encoder.transform([raw_value])[0])
    except Exception as e:
        raise ValueError(f"Unknown label for {col}: {raw_value}") from e

    return encoded


def main():
    raw = {
        "species": "Bangus",
        "province": "Davao del Norte",
        "city": "Panabo City",
        "barangay": "Malaga",
        "fingerlings": 5000,
        "dateFrom": "2024-01-01",
        "dateTo": "2024-03-31",
    }

    encoders: Dict[str, Any] = joblib.load("app/models/label_encoders.pkl")
    scaler = joblib.load("app/models/scaler.pkl")
    model = joblib.load("app/models/unified_fingerlings_regression_model.pkl")

    print("Loaded artifacts:")
    print("  encoders keys:", list(encoders.keys()))
    print("  scaler:", type(scaler), "n_features_in_=", getattr(scaler, "n_features_in_", None))
    print("  model:", type(model), "n_features_in_=", getattr(model, "n_features_in_", None))

    start = datetime.strptime(raw["dateFrom"], "%Y-%m-%d")
    year = start.year
    month = start.month

    print("\nStep 1) Raw input")
    for k in ["species", "province", "city", "barangay", "fingerlings", "dateFrom", "dateTo"]:
        print(f"  {k}: {raw[k]}")
    print("  derived Year:", year)
    print("  derived Month:", month)

    print("\nStep 2) Encode categoricals")
    encoded_species = encode_one(encoders, "Species", raw["species"])
    encoded_barangay = encode_one(encoders, "Barangay", raw["barangay"])
    encoded_municipality = encode_one(encoders, "Municipality", raw["city"])
    encoded_province = encode_one(encoders, "Province", raw["province"])
    print("  Species:", raw["species"], "->", encoded_species)
    print("  Barangay:", raw["barangay"], "->", encoded_barangay)
    print("  Municipality:", raw["city"], "->", encoded_municipality)
    print("  Province:", raw["province"], "->", encoded_province)

    print("\nStep 3) Assemble feature vector (pre-scaling)")
    row: List[float] = [
        float(encoded_species),
        float(encoded_barangay),
        float(encoded_municipality),
        float(encoded_province),
        float(raw["fingerlings"]),
        float(year),
        float(month),
    ]
    X = np.array([row], dtype=float)
    print("  columns:", FEATURE_COLUMNS)
    print("  row:", row)
    print("  shape:", X.shape)

    print("\nStep 4) Apply scaler.transform")
    X_scaled = scaler.transform(X)
    print("  input:", X)
    print("  output:", X_scaled)
    print("  shape:", X_scaled.shape)

    print("\nStep 5) Predict")
    y = model.predict(X_scaled)
    print("  raw model output:", y)
    y0 = float(y[0])
    print("  y0:", y0)

    print("\nStep 6) Call API and compare (same raw strings)")
    resp = requests.post("http://localhost:8000/api/v1/predict", json=raw, timeout=30)
    print("  status:", resp.status_code)
    body = resp.json()
    if resp.status_code != 200:
        print("  error body:", body)
        return

    first_pred = float(body["predictions"][0]["predicted_harvest"])
    print("  api first predicted_harvest:", first_pred)
    print("  delta (api - manual):", first_pred - y0)


if __name__ == "__main__":
    main()

