"""
Audio Preprocessing Pipeline
==============================
Extracts audio features from RAVDESS and CREMA-D speech emotion datasets
and outputs a CSV ready for emotion classifier training.

Datasets:
- RAVDESS: ~1,440 files, 8 emotions, from data/raw/RAVDESS/
- CREMA-D: ~7,442 files, 6 emotions, from data/raw/CREMA-D/

Feature extraction:
- 40 MFCCs (mean + std = 80 features)
- 12 Chroma (mean + std = 24 features)
- 128 Mel spectrogram bands (mean + std = 256 features → reduced to 40 via stats)
- 7 Spectral contrast bands (mean + std = 14 features)
- Zero crossing rate (mean + std = 2 features)
- RMS energy (mean + std = 2 features)
Total: ~162 features per sample

Output: data/interview_emotions_train.csv

Usage:
    python training/preprocessing.py
"""

import os
import sys
import glob
import warnings
import numpy as np
import pandas as pd
import librosa
from pathlib import Path
from collections import Counter

warnings.filterwarnings("ignore", category=UserWarning)

# Add project root to path
PROJECT_ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
sys.path.insert(0, PROJECT_ROOT)


# ─── Configuration ───────────────────────────────────────────────────────────

RAW_DATA_DIR = os.path.join(PROJECT_ROOT, "data", "raw")
OUTPUT_CSV = os.path.join(PROJECT_ROOT, "data", "interview_emotions_train.csv")

# Audio processing params
SAMPLE_RATE = 22050
DURATION = 3.0  # seconds — take first 3 seconds (or pad)
N_MFCC = 40
N_CHROMA = 12
N_MEL = 128
N_CONTRAST = 7

# Project emotion taxonomy (8 classes)
EMOTION_LABELS = [
    "neutral",        # 0
    "calm",           # 1
    "enthusiastic",   # 2
    "hesitant",       # 3
    "frustrated",     # 4
    "nervous",        # 5
    "confident",      # 6
    "engaged",        # 7
]


# ─── RAVDESS Parser ─────────────────────────────────────────────────────────

# RAVDESS filename format: 03-01-{emotion}-{intensity}-{statement}-{rep}-{actor}.wav
# Emotion codes: 01=neutral, 02=calm, 03=happy, 04=sad, 05=angry, 06=fearful, 07=disgust, 08=surprised
RAVDESS_EMOTION_MAP = {
    "01": "neutral",
    "02": "calm",
    "03": "enthusiastic",   # happy → enthusiastic
    "04": "hesitant",       # sad → hesitant
    "05": "frustrated",     # angry → frustrated
    "06": "nervous",        # fearful → nervous
    "07": "frustrated",     # disgust → frustrated
    "08": "engaged",        # surprised → engaged
}


def parse_ravdess(data_dir: str) -> list:
    """
    Parse RAVDESS dataset.
    
    Expected structure:
        data/raw/RAVDESS/Actor_01/03-01-01-01-01-01-01.wav
        data/raw/RAVDESS/Actor_02/...
    
    Returns:
        List of dicts with 'path', 'emotion', 'dataset' keys
    """
    ravdess_dir = os.path.join(data_dir, "RAVDESS")
    if not Path(ravdess_dir).exists():
        print(f"  ⚠️  RAVDESS directory not found: {ravdess_dir}")
        print(f"      Download from: https://zenodo.org/records/1188976")
        print(f"      Place audio files in: {ravdess_dir}/Actor_XX/")
        return []

    samples = []
    audio_files = glob.glob(os.path.join(ravdess_dir, "**", "*.wav"), recursive=True)

    for filepath in audio_files:
        filename = os.path.basename(filepath)
        parts = filename.replace(".wav", "").split("-")

        if len(parts) >= 3:
            emotion_code = parts[2]
            emotion = RAVDESS_EMOTION_MAP.get(emotion_code)
            if emotion:
                samples.append({
                    "path": filepath,
                    "emotion": emotion,
                    "dataset": "RAVDESS",
                })

    print(f"  📂 RAVDESS: Found {len(samples)} samples")
    return samples


# ─── CREMA-D Parser ──────────────────────────────────────────────────────────

# CREMA-D filename format: {actor}_{sentence}_{emotion}_{level}.wav
# Emotion codes: ANG, DIS, FEA, HAP, NEU, SAD
CREMA_EMOTION_MAP = {
    "ANG": "frustrated",
    "DIS": "frustrated",
    "FEA": "nervous",
    "HAP": "enthusiastic",
    "NEU": "neutral",
    "SAD": "hesitant",
}


def parse_crema_d(data_dir: str) -> list:
    """
    Parse CREMA-D dataset.
    
    Expected structure:
        data/raw/CREMA-D/1001_DFA_ANG_XX.wav
        data/raw/CREMA-D/1001_DFA_DIS_XX.wav
        ...
    
    Returns:
        List of dicts with 'path', 'emotion', 'dataset' keys
    """
    crema_dir = os.path.join(data_dir, "CREMA-D")
    if not Path(crema_dir).exists():
        print(f"  ⚠️  CREMA-D directory not found: {crema_dir}")
        print(f"      Download from: https://github.com/CheyneyComputerScience/CREMA-D")
        print(f"      Place audio files in: {crema_dir}/")
        return []

    samples = []
    audio_files = glob.glob(os.path.join(crema_dir, "**", "*.wav"), recursive=True)

    for filepath in audio_files:
        filename = os.path.basename(filepath)
        parts = filename.replace(".wav", "").split("_")

        if len(parts) >= 3:
            emotion_code = parts[2]
            emotion = CREMA_EMOTION_MAP.get(emotion_code)
            if emotion:
                samples.append({
                    "path": filepath,
                    "emotion": emotion,
                    "dataset": "CREMA-D",
                })

    print(f"  📂 CREMA-D: Found {len(samples)} samples")
    return samples


# ─── Feature Extraction ─────────────────────────────────────────────────────

def extract_features(filepath: str) -> np.ndarray:
    """
    Extract audio features from a single WAV file.
    
    Features (concatenated means and stds):
        - 40 MFCCs → 80 features
        - 12 Chroma → 24 features
        - 20 Mel bands (reduced) → 40 features
        - 7 Spectral contrast → 14 features
        - ZCR → 2 features
        - RMS → 2 features
    Total: 162 features
    """
    try:
        # Load audio — fixed duration with padding/truncation
        y, sr = librosa.load(filepath, sr=SAMPLE_RATE, duration=DURATION)

        # Pad if too short
        target_length = int(SAMPLE_RATE * DURATION)
        if len(y) < target_length:
            y = np.pad(y, (0, target_length - len(y)), mode="constant")
        else:
            y = y[:target_length]

        features = []

        # 1. MFCCs (40 coefficients)
        mfcc = librosa.feature.mfcc(y=y, sr=sr, n_mfcc=N_MFCC)
        features.extend(np.mean(mfcc, axis=1))
        features.extend(np.std(mfcc, axis=1))

        # 2. Chroma
        chroma = librosa.feature.chroma_stft(y=y, sr=sr, n_chroma=N_CHROMA)
        features.extend(np.mean(chroma, axis=1))
        features.extend(np.std(chroma, axis=1))

        # 3. Mel spectrogram (reduced to 20 bands via averaging)
        mel = librosa.feature.melspectrogram(y=y, sr=sr, n_mels=N_MEL)
        mel_db = librosa.power_to_db(mel, ref=np.max)
        # Reduce 128 bands to 20 by averaging groups
        n_reduced = 20
        band_size = N_MEL // n_reduced
        mel_reduced = np.array([
            mel_db[i * band_size:(i + 1) * band_size].mean(axis=0)
            for i in range(n_reduced)
        ])
        features.extend(np.mean(mel_reduced, axis=1))
        features.extend(np.std(mel_reduced, axis=1))

        # 4. Spectral contrast
        contrast = librosa.feature.spectral_contrast(y=y, sr=sr, n_bands=N_CONTRAST)
        features.extend(np.mean(contrast, axis=1))
        features.extend(np.std(contrast, axis=1))

        # 5. Zero-crossing rate
        zcr = librosa.feature.zero_crossing_rate(y)
        features.extend([np.mean(zcr), np.std(zcr)])

        # 6. RMS energy
        rms = librosa.feature.rms(y=y)
        features.extend([np.mean(rms), np.std(rms)])

        return np.array(features, dtype=np.float32)

    except Exception as e:
        print(f"    ❌ Error processing {filepath}: {e}")
        return None


# ─── Main Pipeline ───────────────────────────────────────────────────────────

def main():
    print("=" * 60)
    print("  🎙️  Audio Preprocessing Pipeline")
    print("=" * 60)

    # Parse datasets
    print(f"\n📂 Scanning datasets in {RAW_DATA_DIR}...\n")
    all_samples = []
    all_samples.extend(parse_ravdess(RAW_DATA_DIR))
    all_samples.extend(parse_crema_d(RAW_DATA_DIR))

    if not all_samples:
        print("\n❌ No audio data found!")
        print(f"\n📋 To use this preprocessing pipeline:")
        print(f"   1. Download RAVDESS from: https://zenodo.org/records/1188976")
        print(f"      Extract to: {os.path.join(RAW_DATA_DIR, 'RAVDESS')}/Actor_XX/")
        print(f"   2. Download CREMA-D from: https://github.com/CheyneyComputerScience/CREMA-D")
        print(f"      Extract to: {os.path.join(RAW_DATA_DIR, 'CREMA-D')}/")
        print(f"\n   Then re-run: python training/preprocessing.py")

        # Create a small synthetic dataset for testing the pipeline
        print(f"\n🔧 Creating synthetic data for pipeline testing...")
        create_synthetic_data()
        return

    print(f"\n📊 Total samples: {len(all_samples)}")
    print(f"   Emotion distribution:")
    emotion_counts = Counter(s["emotion"] for s in all_samples)
    for emotion, count in sorted(emotion_counts.items(), key=lambda x: -x[1]):
        print(f"     {emotion:15s}: {count:5d}")

    # Extract features
    print(f"\n🧠 Extracting features ({len(all_samples)} files)...\n")

    rows = []
    failed = 0
    for i, sample in enumerate(all_samples):
        features = extract_features(sample["path"])

        if features is not None:
            row = {"emotion": sample["emotion"], "dataset": sample["dataset"]}
            for j, val in enumerate(features):
                row[f"feature_{j}"] = val
            rows.append(row)
        else:
            failed += 1

        # Progress
        if (i + 1) % 200 == 0:
            print(f"  Progress: {i + 1}/{len(all_samples)} ({failed} failed)")

    print(f"\n✅ Feature extraction complete")
    print(f"   Successful: {len(rows)}")
    print(f"   Failed: {failed}")

    # Save CSV
    df = pd.DataFrame(rows)
    os.makedirs(os.path.dirname(OUTPUT_CSV), exist_ok=True)
    df.to_csv(OUTPUT_CSV, index=False)
    print(f"\n💾 Saved to {OUTPUT_CSV}")
    print(f"   Shape: {df.shape}")
    print(f"   Columns: emotion, dataset, feature_0 ... feature_{df.shape[1] - 3}")


def create_synthetic_data():
    """
    Create minimal synthetic data so the training pipeline can be tested
    without downloading full datasets.
    """
    print("  Generating 80 synthetic audio samples (10 per emotion)...\n")

    rows = []
    np.random.seed(42)

    for emotion in EMOTION_LABELS:
        for i in range(10):
            # Generate random audio signal with emotion-specific characteristics
            duration = DURATION
            sr = SAMPLE_RATE
            t = np.linspace(0, duration, int(sr * duration))

            # Different base frequencies per emotion to create variance
            emotion_freq = {
                "neutral": 200, "calm": 150, "enthusiastic": 400,
                "hesitant": 180, "frustrated": 350, "nervous": 300,
                "confident": 250, "engaged": 320,
            }

            freq = emotion_freq.get(emotion, 200) + np.random.uniform(-30, 30)
            y = np.sin(2 * np.pi * freq * t) * 0.3
            y += np.random.normal(0, 0.05, len(y))  # Add noise

            # Save temp file, extract features, delete
            temp_path = os.path.join(PROJECT_ROOT, "data", f"_temp_synth_{emotion}_{i}.wav")
            os.makedirs(os.path.dirname(temp_path), exist_ok=True)

            import soundfile as sf
            sf.write(temp_path, y.astype(np.float32), sr)

            features = extract_features(temp_path)
            os.remove(temp_path)

            if features is not None:
                row = {"emotion": emotion, "dataset": "synthetic"}
                for j, val in enumerate(features):
                    row[f"feature_{j}"] = val
                rows.append(row)

    df = pd.DataFrame(rows)
    os.makedirs(os.path.dirname(OUTPUT_CSV), exist_ok=True)
    df.to_csv(OUTPUT_CSV, index=False)

    print(f"  ✅ Created synthetic dataset: {df.shape}")
    print(f"     Saved to {OUTPUT_CSV}")
    print(f"     ⚠️  This is for pipeline testing only. Use real data for actual training.")
    print(f"\n  Next step: python training/train_emotion.py")


if __name__ == "__main__":
    main()
