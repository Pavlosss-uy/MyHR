import torch
import torch.nn.functional as F
import librosa
import numpy as np
from transformers import Wav2Vec2FeatureExtractor, Wav2Vec2ForSequenceClassification

# --- GLOBAL CONFIG ---
# We load the model once to avoid delays during the interview
MODEL_NAME = "superb/wav2vec2-base-superb-er"
_feature_extractor = None
_model = None

def load_tone_model():
    """Lazy loads the model only when needed."""
    global _feature_extractor, _model
    if _model is None:
        print("Loading Wav2Vec2 Emotion Model... (This may take a moment)")
        try:
            _feature_extractor = Wav2Vec2FeatureExtractor.from_pretrained(MODEL_NAME)
            _model = Wav2Vec2ForSequenceClassification.from_pretrained(MODEL_NAME)
            print("✅ Tone Model Loaded Successfully.")
        except Exception as e:
            print(f"❌ Failed to load Tone Model: {e}")

def analyze_voice_tone(audio_path):
    """
    Analyzes the audio file and returns the dominant emotion and full probability distribution.
    """
    # Ensure model is loaded
    if _model is None:
        load_tone_model()
        if _model is None: 
            return "Unknown", {"Error": "Model not loaded"}

    try:
        # 1. Preprocess Audio
        # Wav2Vec2 expects 16kHz audio. Librosa handles the resampling.
        speech, sr = librosa.load(audio_path, sr=16000)

        # Handle short audio (pad if necessary) or empty audio
        if len(speech) == 0:
            return "Neutral", {"Neutral": "100%"}

        # 2. Prepare Tensors
        inputs = _feature_extractor(
            speech, 
            sampling_rate=16000, 
            return_tensors="pt", 
            padding=True
        )

        # 3. Inference
        with torch.no_grad():
            logits = _model(**inputs).logits

        # 4. Post-processing
        scores = F.softmax(logits, dim=1).detach().cpu().numpy()[0]
        
        # Map labels (neutral, happy, angry, sad)
        labels = _model.config.id2label
        
        # Create readable report
        results = {
            labels[i]: f"{round(score * 100, 1)}%" 
            for i, score in enumerate(scores)
        }

        # Get dominant tone
        top_tone_id = torch.argmax(logits, dim=-1).item()
        top_tone = labels[top_tone_id]

        return top_tone, results

    except Exception as e:
        print(f"Tone Analysis Error: {e}")
        return "Error", {}

# Pre-load on import so the server is ready immediately
load_tone_model()