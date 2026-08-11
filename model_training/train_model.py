"""
Trains the Phase 2 RandomForest flood/blockage/normal classifier on the
8-feature dataset and saves model.joblib + encoder.joblib.

Usage:
    python train_model.py [--dataset dataset.csv] [--output-dir .]

Also copies the resulting model.joblib / encoder.joblib into
../server/models/ so the Flask app picks them up automatically.
"""

import argparse
import os
import shutil

import joblib
import pandas as pd
from sklearn.ensemble import RandomForestClassifier
from sklearn.metrics import accuracy_score, classification_report, confusion_matrix
from sklearn.model_selection import train_test_split
from sklearn.preprocessing import LabelEncoder

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
TARGET = "label"


def train(dataset_path: str, output_dir: str, seed: int = 42):
    df = pd.read_csv(dataset_path)

    missing = [c for c in FEATURES + [TARGET] if c not in df.columns]
    if missing:
        raise ValueError(f"Dataset is missing required columns: {missing}")

    encoder = LabelEncoder()
    X = df[FEATURES]
    y = encoder.fit_transform(df[TARGET])

    print("Classes:")
    for i, name in enumerate(encoder.classes_):
        print(" ", i, "->", name)

    X_train, X_test, y_train, y_test = train_test_split(
        X, y, test_size=0.20, random_state=seed, stratify=y
    )
    print(f"\nTraining samples: {len(X_train)}  |  Testing samples: {len(X_test)}")

    model = RandomForestClassifier(
        n_estimators=300,
        max_depth=18,
        min_samples_split=5,
        min_samples_leaf=3,
        class_weight="balanced",
        random_state=seed,
        n_jobs=-1,
        oob_score=True,
    )

    print("\nTraining...")
    model.fit(X_train, y_train)
    print("Training complete. OOB score:", round(model.oob_score_, 4))

    y_pred = model.predict(X_test)
    print("\nTest accuracy:", round(accuracy_score(y_test, y_pred), 4))
    print("\nClassification report:")
    print(classification_report(y_test, y_pred, target_names=encoder.classes_))
    print("Confusion matrix:")
    print(confusion_matrix(y_test, y_pred))

    importance = pd.DataFrame({
        "Feature": FEATURES,
        "Importance": model.feature_importances_,
    }).sort_values(by="Importance", ascending=False)
    print("\nFeature importance:")
    print(importance.to_string(index=False))

    os.makedirs(output_dir, exist_ok=True)
    model_path = os.path.join(output_dir, "model.joblib")
    encoder_path = os.path.join(output_dir, "encoder.joblib")
    joblib.dump(model, model_path)
    joblib.dump(encoder, encoder_path)
    print(f"\nSaved: {model_path}")
    print(f"Saved: {encoder_path}")

    return model, encoder, model_path, encoder_path


def main():
    here = os.path.dirname(os.path.abspath(__file__))
    parser = argparse.ArgumentParser(description="Train the flood/blockage RandomForest model")
    parser.add_argument("--dataset", default=os.path.join(here, "dataset.csv"))
    parser.add_argument("--output-dir", default=os.path.join(here, "manhole_model_output"))
    parser.add_argument("--seed", type=int, default=42)
    parser.add_argument(
        "--no-deploy",
        action="store_true",
        help="Skip copying the trained artifacts into ../server/models/",
    )
    args = parser.parse_args()

    model, encoder, model_path, encoder_path = train(args.dataset, args.output_dir, args.seed)

    if not args.no_deploy:
        server_models_dir = os.path.join(here, "..", "server", "models")
        os.makedirs(server_models_dir, exist_ok=True)
        shutil.copy2(model_path, os.path.join(server_models_dir, "model.joblib"))
        shutil.copy2(encoder_path, os.path.join(server_models_dir, "encoder.joblib"))
        print(f"\nDeployed model + encoder to {server_models_dir}")


if __name__ == "__main__":
    main()
