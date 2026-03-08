import argparse

import numpy as np
import pandas as pd


def add_yield_ratio(df: pd.DataFrame) -> pd.DataFrame:
    if "actualHarvestKilos" not in df.columns:
        raise ValueError("Missing column: actualHarvestKilos")
    if "fingerlings" not in df.columns:
        raise ValueError("Missing column: fingerlings")

    harvest = pd.to_numeric(df["actualHarvestKilos"], errors="coerce")
    fingerlings = pd.to_numeric(df["fingerlings"], errors="coerce")

    yield_ratio = harvest / fingerlings
    yield_ratio = yield_ratio.replace([np.inf, -np.inf], np.nan)

    mean_yield = float(yield_ratio.dropna().mean()) if yield_ratio.notna().any() else 0.35
    df = df.copy()
    df["yield_ratio"] = yield_ratio.fillna(mean_yield)
    return df


def main():
    parser = argparse.ArgumentParser()
    parser.add_argument("--input", required=True, help="Input CSV path")
    parser.add_argument("--output", required=True, help="Output CSV path")
    args = parser.parse_args()

    df = pd.read_csv(args.input)
    df = add_yield_ratio(df)
    df.to_csv(args.output, index=False)


if __name__ == "__main__":
    main()
