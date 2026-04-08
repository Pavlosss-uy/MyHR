import os
import pandas as pd
import numpy as np
import soundfile as sf

def create_dummy_audio(filepath, sr=16000, duration=2):
    # Create 2 seconds of silent audio (zeros)
    audio = np.zeros(sr * duration)
    sf.write(filepath, audio, sr)

print("Generating dummy audio files...")
os.makedirs('data/raw/dummy', exist_ok=True)

# Generate 16 dummy files (2 for each of our 8 target classes)
labels = ['confident', 'hesitant', 'nervous', 'engaged', 'neutral', 'frustrated', 'enthusiastic', 'uncertain']
data = []

for i, label in enumerate(labels * 2):
    filepath = f"data/raw/dummy/sample_{i}.wav"
    create_dummy_audio(filepath)
    data.append({
        "file_path": filepath, 
        "original_label": "dummy", 
        "target_label": label, 
        "source": "DUMMY"
    })

# Save the CSV directly where the training script expects it
df = pd.DataFrame(data)
os.makedirs('data', exist_ok=True)
df.to_csv("data/interview_emotions_train.csv", index=False)

print("Dummy data created! You can now run the training script.")