import os
import re
import pandas as pd
from pathlib import Path

# Our target 8-class taxonomy
TARGET_EMOTIONS = [
    'confident', 'hesitant', 'nervous', 'engaged', 
    'neutral', 'frustrated', 'enthusiastic', 'uncertain'
]

# -------------------------------------------------------------------
# 1. RAVDESS Mapping & Parsing
# -------------------------------------------------------------------
# RAVDESS filename format: Modality-VocalChannel-Emotion-Intensity-Statement-Repetition-Actor.wav
# Example: 03-01-06-01-02-01-12.wav (06 = fearful)
RAVDESS_EMOTION_MAP = {
    "01": "neutral",        # Neutral
    "02": "confident",      # Calm → confident  (was "neutral")
    "03": "enthusiastic",   # Happy
    "04": "uncertain",      # Sad
    "05": "frustrated",     # Angry
    "06": "nervous",        # Fearful
    "07": "frustrated",     # Disgust
    "08": "engaged",        # Surprised
}

def parse_ravdess(dataset_path):
    """Parses the RAVDESS audio directory and returns a list of dictionaries."""
    data = []
    path = Path(dataset_path)
    
    if not path.exists():
        print(f"Warning: RAVDESS path {dataset_path} not found.")
        return data

    for audio_file in path.rglob("*.wav"):
        filename = audio_file.name
        parts = filename.split('-')
        
        # Ensure it's a valid RAVDESS file
        if len(parts) == 7:
            emotion_code = parts[2]
            target_label = RAVDESS_EMOTION_MAP.get(emotion_code)
            
            if target_label:
                data.append({
                    "file_path": str(audio_file.resolve()),
                    "original_label": emotion_code,
                    "target_label": target_label,
                    "source": "RAVDESS"
                })
    return data

# -------------------------------------------------------------------
# 2. CREMA-D Mapping & Parsing
# -------------------------------------------------------------------
# CREMA-D filename format: {ActorID}_{Sentence}_{Emotion}_{Level}.wav
# Example: 1001_DFA_ANG_XX.wav
# Emotions: ANG (Angry), DIS (Disgust), FEA (Fear), HAP (Happy), NEU (Neutral), SAD (Sad)
CREMA_EMOTION_MAP = {
    "ANG": "frustrated",    # Angry -> frustrated
    "DIS": "frustrated",    # Disgust -> frustrated
    "FEA": "nervous",       # Fear -> nervous
    "HAP": "enthusiastic",  # Happy -> enthusiastic
    "NEU": "neutral",       # Neutral -> neutral
    "SAD": "hesitant",      # Sad -> hesitant
}

def parse_cremad(dataset_path):
    """Parses CREMA-D audio directory and returns a list of dictionaries."""
    data = []
    path = Path(dataset_path)

    if not path.exists():
        print(f"Warning: CREMA-D path {dataset_path} not found.")
        return data

    for audio_file in path.glob("*.wav"):
        filename = audio_file.stem  # e.g., "1001_DFA_ANG_XX"
        parts = filename.split("_")

        if len(parts) >= 3:
            emotion_code = parts[2]  # 3rd field is emotion
            target_label = CREMA_EMOTION_MAP.get(emotion_code)

            if target_label:
                data.append({
                    "file_path": str(audio_file.resolve()),
                    "original_label": emotion_code,
                    "target_label": target_label,
                    "source": "CREMA-D"
                })
    return data


# -------------------------------------------------------------------
# 3. IEMOCAP Mapping & Parsing (kept for completeness)
# -------------------------------------------------------------------
# IEMOCAP labels are found in the EmoEvaluation text files.
IEMOCAP_EMOTION_MAP = {
    "neu": "neutral",
    "hap": "enthusiastic", # Happy
    "exc": "enthusiastic", # Excited
    "sad": "hesitant",     # Sad mapped to hesitant/uncertain
    "ang": "frustrated",   # Angry
    "fru": "frustrated",   # Frustrated
    "fea": "nervous",      # Fearful
    "sur": "engaged",      # Surprised
}

def parse_iemocap(dataset_path):
    """Parses IEMOCAP evaluation files and matches them to audio files."""
    data = []
    path = Path(dataset_path)
    
    if not path.exists():
        print(f"Warning: IEMOCAP path {dataset_path} not found.")
        return data

    for session_dir in path.glob("Session*"):
        eval_dir = session_dir / "dialog" / "EmoEvaluation"
        wav_dir = session_dir / "sentences" / "wav"
        
        if not eval_dir.exists() or not wav_dir.exists():
            continue

        for eval_file in eval_dir.glob("*.txt"):
            with open(eval_file, 'r') as f:
                content = f.read()
                
                pattern = re.compile(r'\[.+\]\s+(Ses\w+)\s+([a-z]{3})\s+\[.+\]')
                matches = pattern.findall(content)
                
                for wav_id, emotion_code in matches:
                    target_label = IEMOCAP_EMOTION_MAP.get(emotion_code)
                    
                    if target_label:
                        impro_id = "_".join(wav_id.split("_")[:2])
                        audio_file = wav_dir / impro_id / f"{wav_id}.wav"
                        
                        if audio_file.exists():
                            data.append({
                                "file_path": str(audio_file.resolve()),
                                "original_label": emotion_code,
                                "target_label": target_label,
                                "source": "IEMOCAP"
                            })
    return data

# -------------------------------------------------------------------
# 4. Main Execution
# -------------------------------------------------------------------
def generate_combined_dataset(ravdess_path, cremad_path, iemocap_path=None, 
                              output_csv="data/interview_emotions_train.csv"):
    print("=" * 60)
    print("  🎵 Emotion Dataset Preprocessing")
    print("=" * 60)

    print("\nParsing RAVDESS dataset...")
    ravdess_data = parse_ravdess(ravdess_path)
    print(f"  Found {len(ravdess_data)} usable RAVDESS samples.")

    print("Parsing CREMA-D dataset...")
    cremad_data = parse_cremad(cremad_path)
    print(f"  Found {len(cremad_data)} usable CREMA-D samples.")

    iemocap_data = []
    if iemocap_path:
        print("Parsing IEMOCAP dataset...")
        iemocap_data = parse_iemocap(iemocap_path)
        print(f"  Found {len(iemocap_data)} usable IEMOCAP samples.")

    # Combine data
    all_data = ravdess_data + cremad_data + iemocap_data
    
    if not all_data:
        print("\n❌ No data parsed. Please check your dataset paths.")
        return

    df = pd.DataFrame(all_data)
    
    # Save to CSV for the dataloader
    os.makedirs(os.path.dirname(output_csv), exist_ok=True)
    df.to_csv(output_csv, index=False)
    
    print(f"\n✅ Combined dataset saved to {output_csv}")
    print(f"   Total samples: {len(df)}")
    print(f"\n📊 Source Distribution:")
    print(df['source'].value_counts().to_string())
    print(f"\n📊 Class Distribution:")
    print(df['target_label'].value_counts().to_string())
    
    # Identify underrepresented classes
    missing = set(TARGET_EMOTIONS) - set(df['target_label'].unique())
    if missing:
        print(f"\n⚠️  Missing classes (0 samples): {missing}")
        print("   These will need synthetic data or alternative mapping.")

if __name__ == "__main__":
    RAVDESS_DIR = "./data/Audio_Speech_Actors_01-24"
    CREMAD_DIR = "./data/archive/AudioWAV"
    IEMOCAP_DIR = "./data/raw/IEMOCAP"  # Optional, may not exist
    
    generate_combined_dataset(RAVDESS_DIR, CREMAD_DIR, IEMOCAP_DIR)