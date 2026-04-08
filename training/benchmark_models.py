import os
import time
import json
import argparse
import tempfile
from pathlib import Path

import librosa
import numpy as np
import pandas as pd
import torch
import torch.nn as nn
import torch.nn.functional as F
from sklearn.metrics import accuracy_score, f1_score, classification_report

from transformers import Wav2Vec2FeatureExtractor, Wav2Vec2ForSequenceClassification

try:
    import onnx
    import onnxruntime as ort
    ONNX_AVAILABLE = True
except Exception:
    ONNX_AVAILABLE = False


MODEL_NAME = "superb/wav2vec2-base-superb-er"
SAMPLE_RATE = 16000

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

LABEL_NORMALIZATION = {
    "neu": "neutral",
    "hap": "happy",
    "ang": "angry",
    "sad": "sad",

    "neutral": "neutral",
    "calm": "calm",
    "happy": "happy",
    "happiness": "happy",
    "sadness": "sad",
    "sad": "sad",
    "angry": "angry",
    "anger": "angry",
    "fear": "fearful",
    "fearful": "fearful",
    "disgust": "disgust",
    "surprise": "surprised",
    "surprised": "surprised",
}

BASE_DIR = Path(__file__).resolve().parent.parent
CHECKPOINT_DIR = BASE_DIR / "models" / "checkpoints"
BENCHMARK_DIR = BASE_DIR / "storage" / "benchmarks"
CHECKPOINT_DIR.mkdir(parents=True, exist_ok=True)
BENCHMARK_DIR.mkdir(parents=True, exist_ok=True)

QUANTIZED_PATH = CHECKPOINT_DIR / "emotion_model_int8_dynamic.pth"
ONNX_PATH = CHECKPOINT_DIR / "emotion_model.onnx"
RESULTS_JSON = BENCHMARK_DIR / "compression_benchmark_results.json"
RESULTS_CSV = BENCHMARK_DIR / "compression_benchmark_results.csv"


def normalize_label(label: str) -> str:
    if label is None:
        return None
    return LABEL_NORMALIZATION.get(str(label).strip().lower(), str(label).strip().lower())


def parse_ravdess_filename(filename: str):
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

    return pd.DataFrame(rows)


def load_base_model():
    print(f"Loading model: {MODEL_NAME}")
    feature_extractor = Wav2Vec2FeatureExtractor.from_pretrained(MODEL_NAME)
    model = Wav2Vec2ForSequenceClassification.from_pretrained(MODEL_NAME)
    model.eval()

    model_labels = [
        normalize_label(v)
        for _, v in sorted(model.config.id2label.items())
    ]
    return feature_extractor, model, model_labels


def get_file_size_mb(path: Path) -> float:
    if not path.exists():
        return 0.0
    return round(path.stat().st_size / (1024 * 1024), 2)


def estimate_model_size_mb(model: torch.nn.Module) -> float:
    with tempfile.NamedTemporaryFile(suffix=".pth", delete=False) as tmp:
        temp_path = Path(tmp.name)

    try:
        torch.save(model.state_dict(), temp_path)
        return get_file_size_mb(temp_path)
    finally:
        if temp_path.exists():
            temp_path.unlink(missing_ok=True)


def quantize_model_dynamic(model):
    print("Applying dynamic INT8 quantization...")
    quantized_model = torch.quantization.quantize_dynamic(
        model,
        {nn.Linear},
        dtype=torch.qint8
    )
    quantized_model.eval()
    return quantized_model


def save_quantized_model(quantized_model, path: Path):
    torch.save(quantized_model.state_dict(), path)


def export_to_onnx(model, onnx_path: Path):
    if not ONNX_AVAILABLE:
        print("ONNX not installed. Skipping export.")
        return False

    print(f"Exporting ONNX model to: {onnx_path}")

    dummy_input = torch.randn(1, SAMPLE_RATE * 5, dtype=torch.float32)

    torch.onnx.export(
        model,
        dummy_input,
        str(onnx_path),
        input_names=["input_values"],
        output_names=["logits"],
        dynamic_axes={
            "input_values": {0: "batch_size", 1: "sequence_length"},
            "logits": {0: "batch_size"},
        },
        opset_version=14,
        do_constant_folding=True,
    )

    onnx_model = onnx.load(str(onnx_path))
    onnx.checker.check_model(onnx_model)
    return True


def prepare_inputs(feature_extractor, audio_path: str):
    speech, sr = librosa.load(audio_path, sr=SAMPLE_RATE)
    if len(speech) == 0:
        return None
    return feature_extractor(
        speech,
        sampling_rate=SAMPLE_RATE,
        return_tensors="pt",
        padding=True,
    )


def predict_torch(model, feature_extractor, audio_path: str):
    inputs = prepare_inputs(feature_extractor, audio_path)
    if inputs is None:
        return None, None, None

    start = time.perf_counter()
    with torch.no_grad():
        logits = model(**inputs).logits
    elapsed_ms = (time.perf_counter() - start) * 1000.0

    probs = F.softmax(logits, dim=-1).detach().cpu().numpy()[0]
    pred_id = int(torch.argmax(logits, dim=-1).item())
    pred_label_raw = model.config.id2label[pred_id]
    pred_label = normalize_label(pred_label_raw)

    return pred_label, probs, elapsed_ms


def predict_onnx(session, feature_extractor, model_id2label, audio_path: str):
    inputs = prepare_inputs(feature_extractor, audio_path)
    if inputs is None:
        return None, None, None

    input_values = inputs["input_values"].detach().cpu().numpy()

    start = time.perf_counter()
    outputs = session.run(None, {"input_values": input_values})
    elapsed_ms = (time.perf_counter() - start) * 1000.0

    logits = outputs[0]
    probs = torch.softmax(torch.tensor(logits), dim=-1).numpy()[0]
    pred_id = int(np.argmax(logits, axis=-1)[0])
    pred_label_raw = model_id2label[pred_id]
    pred_label = normalize_label(pred_label_raw)

    return pred_label, probs, elapsed_ms


def evaluate_variant(
    variant_name: str,
    df: pd.DataFrame,
    feature_extractor,
    predict_fn,
):
    y_true = []
    y_pred = []
    inference_times = []

    for idx, row in df.iterrows():
        try:
            pred_label, probs, elapsed_ms = predict_fn(row["path"])
            if pred_label is None:
                continue

            y_true.append(row["true_label"])
            y_pred.append(pred_label)
            inference_times.append(elapsed_ms)

            if len(y_true) % 100 == 0:
                print(f"[{variant_name}] Processed {len(y_true)} files...")

        except Exception as e:
            print(f"[{variant_name}] Error processing {row['path']}: {e}")

    if not y_true:
        return {
            "version": variant_name,
            "samples": 0,
            "accuracy": 0.0,
            "weighted_f1": 0.0,
            "macro_f1": 0.0,
            "avg_inference_ms": 0.0,
            "classification_report": {},
        }

    labels_for_eval = sorted(list(set(y_true) | set(y_pred)))

    acc = accuracy_score(y_true, y_pred)
    weighted_f1 = f1_score(y_true, y_pred, average="weighted")
    macro_f1 = f1_score(y_true, y_pred, average="macro")

    report = classification_report(
        y_true,
        y_pred,
        labels=labels_for_eval,
        output_dict=True,
        zero_division=0,
    )

    return {
        "version": variant_name,
        "samples": len(y_true),
        "accuracy": round(acc, 4),
        "weighted_f1": round(weighted_f1, 4),
        "macro_f1": round(macro_f1, 4),
        "avg_inference_ms": round(sum(inference_times) / len(inference_times), 2),
        "classification_report": report,
    }


def main():
    parser = argparse.ArgumentParser(description="Benchmark FP32 vs INT8 vs ONNX on RAVDESS.")
    parser.add_argument(
        "--data_root",
        type=str,
        required=True,
        help="Path to RAVDESS speech root, e.g. D:\\College\\GP\\archive\\audio_speech_actors_01-24"
    )
    args = parser.parse_args()

    df = collect_ravdess_files(args.data_root)
    if df.empty:
        print("No WAV files found.")
        return

    print(f"Found {len(df)} audio files.")

    feature_extractor, base_model, model_labels = load_base_model()
    model_label_set = set(model_labels)

    dataset_label_set = set(df["true_label"].unique())
    print("Dataset labels:", sorted(dataset_label_set))
    print("Model labels:", sorted(model_label_set))
    print("Overlapping labels:", sorted(dataset_label_set & model_label_set))

    df["is_supported"] = df["true_label"].apply(lambda x: x in model_label_set)
    supported_df = df[df["is_supported"]].copy()
    skipped_df = df[~df["is_supported"]].copy()

    print(f"Supported files: {len(supported_df)}")
    print(f"Skipped files: {len(skipped_df)}")

    if supported_df.empty:
        print("No overlapping labels to evaluate.")
        return

    benchmark_rows = []

    # 1) FP32
    print("\n=== FP32 Evaluation ===")
    fp32_result = evaluate_variant(
        "Original FP32",
        supported_df,
        feature_extractor,
        lambda audio_path: predict_torch(base_model, feature_extractor, audio_path),
    )
    fp32_result["size_mb"] = estimate_model_size_mb(base_model)
    benchmark_rows.append(fp32_result)

    # 2) INT8 Quantized
    print("\n=== INT8 Evaluation ===")
    quant_model = quantize_model_dynamic(base_model)
    save_quantized_model(quant_model, QUANTIZED_PATH)

    int8_result = evaluate_variant(
        "INT8 Quantized",
        supported_df,
        feature_extractor,
        lambda audio_path: predict_torch(quant_model, feature_extractor, audio_path),
    )
    int8_result["size_mb"] = get_file_size_mb(QUANTIZED_PATH)
    benchmark_rows.append(int8_result)

    # 3) ONNX
    print("\n=== ONNX Evaluation ===")
    if ONNX_AVAILABLE and export_to_onnx(base_model, ONNX_PATH):
        ort_session = ort.InferenceSession(str(ONNX_PATH), providers=["CPUExecutionProvider"])
        model_id2label = base_model.config.id2label

        onnx_result = evaluate_variant(
            "ONNX Runtime",
            supported_df,
            feature_extractor,
            lambda audio_path: predict_onnx(
                ort_session,
                feature_extractor,
                model_id2label,
                audio_path,
            ),
        )
        onnx_result["size_mb"] = get_file_size_mb(ONNX_PATH)
    else:
        onnx_result = {
            "version": "ONNX Runtime",
            "samples": 0,
            "accuracy": None,
            "weighted_f1": None,
            "macro_f1": None,
            "avg_inference_ms": None,
            "size_mb": None,
            "classification_report": {},
        }

    benchmark_rows.append(onnx_result)

    # Save machine-readable results
    with open(RESULTS_JSON, "w", encoding="utf-8") as f:
        json.dump(benchmark_rows, f, indent=2)

    # Save compact table
    compact_rows = []
    for row in benchmark_rows:
        compact_rows.append({
            "Version": row["version"],
            "Size (MB)": row["size_mb"],
            "Samples": row["samples"],
            "Accuracy": row["accuracy"],
            "Weighted F1": row["weighted_f1"],
            "Macro F1": row["macro_f1"],
            "Avg Inference (ms)": row["avg_inference_ms"],
        })

    pd.DataFrame(compact_rows).to_csv(RESULTS_CSV, index=False, encoding="utf-8")

    print("\n=== Final Benchmark Table ===")
    for row in compact_rows:
        print(row)

    print(f"\nSaved JSON: {RESULTS_JSON}")
    print(f"Saved CSV:  {RESULTS_CSV}")


if __name__ == "__main__":
    main()