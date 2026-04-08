import os
import argparse
from pathlib import Path

import librosa
import numpy as np
import pandas as pd
import torch
import torch.nn.functional as F
from sklearn.metrics import (
    accuracy_score,
    f1_score,
    classification_report,
    confusion_matrix,
)
from transformers import Wav2Vec2FeatureExtractor, Wav2Vec2ForSequenceClassification


MODEL_NAME = "superb/wav2vec2-base-superb-er"
SAMPLE_RATE = 16000

# RAVDESS emotion code mapping
RAVDESS_EMOTION_MAP = {
    "01": "neutral",
    "02": "calm",
    "03": "happy",
    "04": "sad",
    "05": "angry",
    "06": "fearful",
    "07": "disgust",
    "08": "surprised",
}

# Normalize label text across datasets / models
LABEL_NORMALIZATION = {
    # model short labels
    "neu": "neutral",
    "hap": "happy",
    "ang": "angry",
    "sad": "sad",

    # full labels
    "neutral": "neutral",
    "calm": "calm",
    "happy": "happy",
    "happiness": "happy",
    "sad": "sad",
    "sadness": "sad",
    "angry": "angry",
    "anger": "angry",
    "fear": "fearful",
    "fearful": "fearful",
    "disgust": "disgust",
    "surprise": "surprised",
    "surprised": "surprised",
}


def normalize_label(label: str) -> str:
    if label is None:
        return None
    label = str(label).strip().lower()
    return LABEL_NORMALIZATION.get(label, label)


def parse_ravdess_filename(filename: str):
    """
    Example filename:
    03-01-05-01-01-01-01.wav

    The 3rd field is emotion code.
    """
    stem = Path(filename).stem
    parts = stem.split("-")
    if len(parts) != 7:
        return None

    emotion_code = parts[2]
    actor_id = parts[6]

    if emotion_code not in RAVDESS_EMOTION_MAP:
        return None

    return {
        "emotion_code": emotion_code,
        "emotion_label": normalize_label(RAVDESS_EMOTION_MAP[emotion_code]),
        "actor_id": actor_id,
    }


def collect_ravdess_files(dataset_root: str):
    rows = []

    for root, _, files in os.walk(dataset_root):
        for file in files:
            if not file.lower().endswith(".wav"):
                continue

            parsed = parse_ravdess_filename(file)
            if parsed is None:
                continue

            rows.append({
                "path": os.path.join(root, file),
                "filename": file,
                "emotion_code": parsed["emotion_code"],
                "true_label": parsed["emotion_label"],
                "actor_id": parsed["actor_id"],
            })

    df = pd.DataFrame(rows)
    return df


def load_model():
    print(f"Loading model: {MODEL_NAME}")
    feature_extractor = Wav2Vec2FeatureExtractor.from_pretrained(MODEL_NAME)
    model = Wav2Vec2ForSequenceClassification.from_pretrained(MODEL_NAME)
    model.eval()

    id2label = model.config.id2label
    model_labels = [normalize_label(v) for _, v in sorted(id2label.items())]

    print("Model labels:", model_labels)
    return feature_extractor, model, model_labels


def predict_emotion(audio_path: str, feature_extractor, model):
    speech, sr = librosa.load(audio_path, sr=SAMPLE_RATE)

    if len(speech) == 0:
        return None, None

    inputs = feature_extractor(
        speech,
        sampling_rate=SAMPLE_RATE,
        return_tensors="pt",
        padding=True,
    )

    with torch.no_grad():
        logits = model(**inputs).logits

    probs = F.softmax(logits, dim=-1).detach().cpu().numpy()[0]
    pred_id = int(torch.argmax(logits, dim=-1).item())
    pred_label_raw = model.config.id2label[pred_id]
    pred_label = normalize_label(pred_label_raw)

    return pred_label, probs


def main():
    parser = argparse.ArgumentParser()
    parser.add_argument(
        "--data_root",
        type=str,
        required=True,
        help="Root path of RAVDESS dataset, e.g. D:\\College\\GP\\archive",
    )
    parser.add_argument(
        "--output_dir",
        type=str,
        default="storage/benchmarks/ravdess_eval",
        help="Directory to save evaluation outputs",
    )
    args = parser.parse_args()

    output_dir = Path(args.output_dir)
    output_dir.mkdir(parents=True, exist_ok=True)

    # 1) Collect dataset files
    df = collect_ravdess_files(args.data_root)
    if df.empty:
        print("No WAV files found. Check your dataset path.")
        return

    print(f"Found {len(df)} audio files.")

    # 2) Load model
    feature_extractor, model, model_labels = load_model()
    model_label_set = set(model_labels)

    dataset_label_set = set(df["true_label"].unique())
    print("Dataset labels:", sorted(dataset_label_set))
    print("Overlapping labels:", sorted(dataset_label_set & model_label_set))

    # 3) Filter to overlapping labels only
    df["is_supported"] = df["true_label"].apply(lambda x: x in model_label_set)
    supported_df = df[df["is_supported"]].copy()
    skipped_df = df[~df["is_supported"]].copy()

    print(f"Supported files: {len(supported_df)}")
    print(f"Skipped files (unsupported labels): {len(skipped_df)}")

    if supported_df.empty:
        print("No overlapping labels between RAVDESS and model labels.")
        print("Model labels:", sorted(model_label_set))
        return

    # 4) Run inference
    y_true = []
    y_pred = []
    detailed_rows = []

    for idx, row in supported_df.iterrows():
        audio_path = row["path"]
        true_label = row["true_label"]

        try:
            pred_label, probs = predict_emotion(audio_path, feature_extractor, model)

            if pred_label is None:
                continue

            y_true.append(true_label)
            y_pred.append(pred_label)

            detailed_rows.append({
                "path": audio_path,
                "filename": row["filename"],
                "actor_id": row["actor_id"],
                "true_label": true_label,
                "pred_label": pred_label,
                "correct": int(true_label == pred_label),
            })

            if len(detailed_rows) % 100 == 0:
                print(f"Processed {len(detailed_rows)} files...")

        except Exception as e:
            print(f"Error processing {audio_path}: {e}")

    if not y_true:
        print("No predictions were generated.")
        return

    # 5) Metrics
    labels_for_eval = sorted(list(set(y_true) | set(y_pred)))

    acc = accuracy_score(y_true, y_pred)
    weighted_f1 = f1_score(y_true, y_pred, average="weighted")
    macro_f1 = f1_score(y_true, y_pred, average="macro")

    report_dict = classification_report(
        y_true,
        y_pred,
        labels=labels_for_eval,
        output_dict=True,
        zero_division=0,
    )

    report_text = classification_report(
        y_true,
        y_pred,
        labels=labels_for_eval,
        zero_division=0,
    )

    cm = confusion_matrix(y_true, y_pred, labels=labels_for_eval)
    cm_df = pd.DataFrame(cm, index=labels_for_eval, columns=labels_for_eval)

    # 6) Save outputs
    detailed_df = pd.DataFrame(detailed_rows)
    detailed_csv = output_dir / "predictions.csv"
    report_csv = output_dir / "classification_report.csv"
    cm_csv = output_dir / "confusion_matrix.csv"
    summary_txt = output_dir / "summary.txt"
    skipped_csv = output_dir / "skipped_unsupported_labels.csv"

    detailed_df.to_csv(detailed_csv, index=False, encoding="utf-8")
    pd.DataFrame(report_dict).transpose().to_csv(report_csv, encoding="utf-8")
    cm_df.to_csv(cm_csv, encoding="utf-8")
    skipped_df.to_csv(skipped_csv, index=False, encoding="utf-8")

    with open(summary_txt, "w", encoding="utf-8") as f:
        f.write(f"Model: {MODEL_NAME}\n")
        f.write(f"Dataset root: {args.data_root}\n")
        f.write(f"Total WAV files found: {len(df)}\n")
        f.write(f"Supported files evaluated: {len(y_true)}\n")
        f.write(f"Skipped unsupported files: {len(skipped_df)}\n")
        f.write(f"Accuracy: {acc:.4f}\n")
        f.write(f"Weighted F1: {weighted_f1:.4f}\n")
        f.write(f"Macro F1: {macro_f1:.4f}\n\n")
        f.write("Classification Report\n")
        f.write("=====================\n")
        f.write(report_text)

    # 7) Print summary
    print("\n=== Evaluation Summary ===")
    print(f"Accuracy:     {acc:.4f}")
    print(f"Weighted F1:  {weighted_f1:.4f}")
    print(f"Macro F1:     {macro_f1:.4f}")
    print(f"Predictions:  {detailed_csv}")
    print(f"Report:       {report_csv}")
    print(f"Conf Matrix:  {cm_csv}")
    print(f"Summary:      {summary_txt}")
    print(f"Skipped:      {skipped_csv}")


if __name__ == "__main__":
    main()