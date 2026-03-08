import argparse
from pathlib import Path

import joblib
import pandas as pd
from sklearn.linear_model import LinearRegression
from sklearn.preprocessing import OrdinalEncoder, StandardScaler


FEATURES = ["Species", "Barangay", "Municipality", "Province", "Fingerlings", "Year", "Month"]
CATEGORICAL_COLS = ["Species", "Barangay", "Municipality", "Province"]


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

    for col in CATEGORICAL_COLS:
        X[col] = (
            X[col]
            .astype(str)
            .str.strip()
            .str.split()
            .str.join(" ")
            .str.title()
        )

    categorical_encoder = OrdinalEncoder(handle_unknown="use_encoded_value", unknown_value=-1)
    X[CATEGORICAL_COLS] = categorical_encoder.fit_transform(X[CATEGORICAL_COLS])

    X = X.astype(float)
    scaler = StandardScaler()
    X_scaled = scaler.fit_transform(X)

    model = LinearRegression()
    model.fit(X_scaled, y)

    out_dir = Path(args.output_dir)
    out_dir.mkdir(parents=True, exist_ok=True)

    joblib.dump(model, out_dir / "unified_model.pkl")
    joblib.dump(categorical_encoder, out_dir / "categorical_encoder.pkl")
    joblib.dump(scaler, out_dir / "scaler.pkl")


if __name__ == "__main__":
    main()
