import pandas as pd
import torch
import librosa
from torch.utils.data import Dataset
from transformers import Wav2Vec2FeatureExtractor # Changed this import

class InterviewEmotionDataset(Dataset):
    def __init__(self, csv_file, model_name="superb/wav2vec2-base-superb-er", max_length_seconds=5):
        self.data = pd.read_csv(csv_file)
        # Use FeatureExtractor instead of Processor
        self.feature_extractor = Wav2Vec2FeatureExtractor.from_pretrained(model_name)
        self.max_length = max_length_seconds * 16000 # 16kHz sample rate
        
        self.label_map = {
            'confident': 0, 'hesitant': 1, 'nervous': 2, 'engaged': 3,
            'neutral': 4, 'frustrated': 5, 'enthusiastic': 6, 'uncertain': 7
        }
        
    def __len__(self):
        return len(self.data)
        
    def __getitem__(self, idx):
        row = self.data.iloc[idx]
        audio_path = row['file_path']
        label_str = row['target_label']
        
        speech, _ = librosa.load(audio_path, sr=16000)
        
        # Use the feature_extractor here
        inputs = self.feature_extractor(
            speech, 
            sampling_rate=16000, 
            return_tensors="pt", 
            padding="max_length", 
            max_length=self.max_length, 
            truncation=True
        )
        
        label_idx = self.label_map[label_str]
        
        return {
            'input_values': inputs.input_values.squeeze(0),
            'attention_mask': inputs.attention_mask.squeeze(0),
            'labels': torch.tensor(label_idx, dtype=torch.long)
        }