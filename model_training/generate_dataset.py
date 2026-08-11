"""
Synthetic dataset generator for the Phase 2 flood/blockage detection model.

Produces a CSV with exactly these 8 features + label:

    water_level_node1
    water_level_node2
    level_diff                         (= water_level_node1 - water_level_node2)
    rise_rate_node1
    rise_rate_node2
    precipitationIntensity
    precipitationProbability
    precipitationIntensity_next_hour
    label                              (normal | flood | blockage)

Usage:
    python generate_dataset.py [--output dataset.csv] [--normal 3000] [--flood 1500] [--blockage 1500]
"""

import argparse
import os

import numpy as np
import pandas as pd

FEATURES = [
    "water_level_node1",
    "water_level_node2",
    "level_diff",
    "rise_rate_node1",
    "rise_rate_node2",
    "precipitationIntensity",
    "precipitationProbability",
    "precipitationIntensity_next_hour",
]


def generate_normal(n: int) -> pd.DataFrame:
    rows = []
    for _ in range(n):
        rain_probability = np.random.uniform(0, 40)

        precipitation_intensity = max(0, rain_probability * 0.08 + np.random.normal(0, 1))
        precipitation_intensity_next = max(0, precipitation_intensity + np.random.normal(0, 1))

        rise_rate1 = max(0, precipitation_intensity * 0.20 + np.random.uniform(0, 1))
        rise_rate2 = max(0, rise_rate1 + np.random.uniform(-0.3, 0.3))

        base_level = np.random.uniform(2, 12)
        water_level1 = base_level + rise_rate1 * np.random.uniform(0.2, 0.5)
        water_level2 = np.clip(water_level1 + np.random.uniform(-1.5, 1.5), 1, 15)

        level_difference = water_level1 - water_level2

        rows.append([
            water_level1, water_level2, level_difference,
            rise_rate1, rise_rate2,
            precipitation_intensity, rain_probability, precipitation_intensity_next,
            "normal",
        ])

    return pd.DataFrame(rows, columns=FEATURES + ["label"])


def generate_flood(n: int) -> pd.DataFrame:
    rows = []
    for _ in range(n):
        rain_probability = np.random.uniform(75, 100)
        precipitation_intensity = np.random.uniform(25, 80)
        precipitation_intensity_next = np.clip(
            precipitation_intensity + np.random.uniform(-5, 20), 20, 100
        )

        rise_rate1 = precipitation_intensity * 0.25 + np.random.uniform(2, 6)
        rise_rate2 = rise_rate1 + np.random.uniform(-1, 1)

        water_level1 = np.clip(15 + rise_rate1 + np.random.uniform(0, 8), 18, 35)
        water_level2 = np.clip(water_level1 + np.random.uniform(-2, 2), 18, 35)

        level_difference = water_level1 - water_level2

        rows.append([
            water_level1, water_level2, level_difference,
            rise_rate1, rise_rate2,
            precipitation_intensity, rain_probability, precipitation_intensity_next,
            "flood",
        ])

    return pd.DataFrame(rows, columns=FEATURES + ["label"])


def generate_blockage(n: int) -> pd.DataFrame:
    rows = []
    for _ in range(n):
        rain_probability = np.random.uniform(0, 100)
        precipitation_intensity = np.random.uniform(0, 40)
        precipitation_intensity_next = max(
            0, precipitation_intensity + np.random.uniform(-5, 10)
        )

        rise_rate1 = np.random.uniform(8, 18)
        rise_rate2 = np.random.uniform(-0.5, 1.5)

        water_level1 = np.random.uniform(22, 35)
        blockage_factor = np.random.uniform(12, 28)
        water_level2 = max(1, water_level1 - blockage_factor)

        level_difference = water_level1 - water_level2

        rows.append([
            water_level1, water_level2, level_difference,
            rise_rate1, rise_rate2,
            precipitation_intensity, rain_probability, precipitation_intensity_next,
            "blockage",
        ])

    return pd.DataFrame(rows, columns=FEATURES + ["label"])


def build_dataset(n_normal: int, n_flood: int, n_blockage: int, seed: int = 42) -> pd.DataFrame:
    np.random.seed(seed)

    df = pd.concat([
        generate_normal(n_normal),
        generate_flood(n_flood),
        generate_blockage(n_blockage),
    ], ignore_index=True)

    numeric_cols = df.select_dtypes(include=np.number).columns
    for col in numeric_cols:
        df[col] += np.random.normal(0, 0.2, len(df))

    df = df.sample(frac=1, random_state=seed).reset_index(drop=True)
    return df


def main():
    parser = argparse.ArgumentParser(description="Generate the synthetic flood/blockage dataset")
    parser.add_argument("--output", default=os.path.join(os.path.dirname(__file__), "dataset.csv"))
    parser.add_argument("--normal", type=int, default=3000)
    parser.add_argument("--flood", type=int, default=1500)
    parser.add_argument("--blockage", type=int, default=1500)
    parser.add_argument("--seed", type=int, default=42)
    args = parser.parse_args()

    df = build_dataset(args.normal, args.flood, args.blockage, args.seed)
    df.to_csv(args.output, index=False)

    print(df.head())
    print()
    print(df["label"].value_counts())
    print()
    print("Dataset size:", len(df))
    print("Saved:", args.output)


if __name__ == "__main__":
    main()
