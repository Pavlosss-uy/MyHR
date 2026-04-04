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
    "01": "neutral",       # Neutral -> neutral
    "02": "neutral",       # Calm -> neutral
    "03": "enthusiastic",  # Happy -> enthusiastic
    "04": "uncertain",     # Sad -> uncertain / hesitant
    "05": "frustrated",    # Angry -> frustrated
    "06": "nervous",       # Fearful -> nervous
    "07": "frustrated",    # Disgust -> frustrated
    "08": "engaged"        # Surprised -> engaged
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
# 2. IEMOCAP Mapping & Parsing
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
    # IEMOCAP also has 'xxx' (unclassified) and 'oth' (other) which we will ignore.
}

def parse_iemocap(dataset_path):
    """Parses IEMOCAP evaluation files and matches them to audio files."""
    data = []
    path = Path(dataset_path)
    
    if not path.exists():
        print(f"Warning: IEMOCAP path {dataset_path} not found.")
        return data

    # Find all evaluation files
    for session_dir in path.glob("Session*"):
        eval_dir = session_dir / "dialog" / "EmoEvaluation"
        wav_dir = session_dir / "sentences" / "wav"
        
        if not eval_dir.exists() or not wav_dir.exists():
            continue

        for eval_file in eval_dir.glob("*.txt"):
            with open(eval_file, 'r') as f:
                content = f.read()
                
                # Regex to extract the filename and the emotion label
                # Example line: [00:06.2900 - 00:08.2300]	Ses01F_impro01_F000	neu	[2.5000, 2.5000, 2.5000]
                pattern = re.compile(r'\[.+\]\s+(Ses\w+)\s+([a-z]{3})\s+\[.+\]')
                matches = pattern.findall(content)
                
                for wav_id, emotion_code in matches:
                    target_label = IEMOCAP_EMOTION_MAP.get(emotion_code)
                    
                    if target_label:
                        # Construct path to the actual wav chunk
                        # e.g., Session1/sentences/wav/Ses01F_impro01/Ses01F_impro01_F000.wav
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
# 3. Main Execution
# -------------------------------------------------------------------
def generate_combined_dataset(ravdess_path, iemocap_path, output_csv="data/interview_emotions_train.csv"):
    print("Parsing RAVDESS dataset...")
    ravdess_data = parse_ravdess(ravdess_path)
    print(f"Found {len(ravdess_data)} usable RAVDESS samples.")

    print("Parsing IEMOCAP dataset...")
    iemocap_data = parse_iemocap(iemocap_path)
    print(f"Found {len(iemocap_data)} usable IEMOCAP samples.")

    # Combine data
    all_data = ravdess_data + iemocap_data
    
    if not all_data:
        print("No data parsed. Please check your dataset paths.")
        return

    df = pd.DataFrame(all_data)
    
    # Save to CSV for the dataloader
    os.makedirs(os.path.dirname(output_csv), exist_ok=True)
    df.to_csv(output_csv, index=False)
    
    print(f"\nSuccessfully combined datasets! Saved to {output_csv}")
    print("\nClass Distribution:")
    print(df['target_label'].value_counts())
    
    # Identify underrepresented classes that need synthetic data
    print("\nNote: Classes with 0 or very low counts (like 'confident') will need to be populated via the synthetic data generator.")

if __name__ == "__main__":
    # TODO: Update these paths to where you have extracted the datasets on your machine
    RAVDESS_DIR = "./data/raw/RAVDESS"
    IEMOCAP_DIR = "./data/raw/IEMOCAP"
    
    generate_combined_dataset(RAVDESS_DIR, IEMOCAP_DIR)