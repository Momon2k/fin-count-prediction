import argparse
from pathlib import Path

import joblib
import pandas as pd
from sklearn.linear_model import LinearRegression
from sklearn.preprocessing import LabelEncoder, StandardScaler


FEATURES = ["Species", "Barangay", "Municipality", "Province", "Fingerlings", "Year", "Month"]


def main():
    parser = argparse.ArgumentParser()
    parser.add_argument("--input", required=True, help="Prepared CSV path (must include yield_ratio)")
    parser.add_argument(
        "--output-dir",
        default=str(Path("app") / "models"),
        help="Directory to write model artifacts into",
    )
    args = parser.parse_args()

    df = pd.read_csv(args.input)
    if "yield_ratio" not in df.columns:
        raise ValueError("Missing column: yield_ratio (run training/prepare_dataset.py first)")

    X = df[FEATURES].copy()
    y = pd.to_numeric(df["yield_ratio"], errors="coerce").fillna(df["yield_ratio"].mean())

    label_encoders = {}
    for col in ["Species", "Barangay", "Municipality", "Province"]:
        le = LabelEncoder()
        X[col] = le.fit_transform(X[col].astype(str))
        label_encoders[col] = le

    X = X.astype(float)
    scaler = StandardScaler()
    X_scaled = scaler.fit_transform(X)

    model = LinearRegression()
    model.fit(X_scaled, y)

    out_dir = Path(args.output_dir)
    out_dir.mkdir(parents=True, exist_ok=True)

    joblib.dump(model, out_dir / "unified_model.pkl")
    joblib.dump(label_encoders, out_dir / "label_encoders.pkl")
    joblib.dump(scaler, out_dir / "scaler.pkl")


if __name__ == "__main__":
    main()
