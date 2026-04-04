import torch
import torch.nn as nn
from transformers import Wav2Vec2Model, Wav2Vec2FeatureExtractor
import librosa

class InterviewEmotionModel(nn.Module):
    def __init__(self, model_name="superb/wav2vec2-base-superb-er", num_classes=8):
        super(InterviewEmotionModel, self).__init__()
        
        self.feature_extractor = Wav2Vec2FeatureExtractor.from_pretrained(model_name)
        self.wav2vec2 = Wav2Vec2Model.from_pretrained(model_name)
        
        # Freeze the feature extractor to retain acoustic learning
        self.wav2vec2.feature_extractor._freeze_parameters()
        
        self.classifier = nn.Sequential(
            nn.Linear(768, 256),
            nn.LayerNorm(256),
            nn.GELU(),
            nn.Dropout(0.3),
            nn.Linear(256, 128),
            nn.LayerNorm(128),
            nn.GELU(),
            nn.Dropout(0.3),
            nn.Linear(128, num_classes)
        )
        
        self.labels = [
            'confident', 'hesitant', 'nervous', 'engaged', 
            'neutral', 'frustrated', 'enthusiastic', 'uncertain'
        ]

    def forward(self, input_values, attention_mask=None):
        outputs = self.wav2vec2(input_values=input_values, attention_mask=attention_mask)
        
        # Get the sequence output (Shape: [Batch, 249, 768])
        hidden_states = outputs.last_hidden_state
        
        # FIX: Simply take the mean over the sequence length dimension (dim=1)
        # Wav2Vec2 already applied the attention mask internally during its transformer layers.
        pooled_output = torch.mean(hidden_states, dim=1)
            
        logits = self.classifier(pooled_output)
        return logits

    def predict_from_audio(self, audio_path):
        self.eval()
        speech, _ = librosa.load(audio_path, sr=16000)
        
        inputs = self.feature_extractor(speech, sampling_rate=16000, return_tensors="pt", padding=True)
        
        with torch.no_grad():
            logits = self.forward(inputs.input_values, inputs.attention_mask)
            probabilities = torch.nn.functional.softmax(logits, dim=-1)
            
        pred_idx = torch.argmax(probabilities, dim=-1).item()
        confidence = probabilities[0][pred_idx].item()
        
        return {
            "dominant_tone": self.labels[pred_idx],
            "confidence": confidence,
            "tone_profile": probabilities[0].tolist() 
        }