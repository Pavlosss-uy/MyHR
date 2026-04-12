import torch
import torch.nn as nn
import numpy as np
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

    @staticmethod
    def _fallback_result():
        """Guaranteed-valid fallback when inference cannot run."""
        return {
            "dominant_tone": "neutral",
            "confidence": 0.5,
            "tone_profile": [0.0, 0.0, 0.0, 0.0, 1.0, 0.0, 0.0, 0.0],  # neutral=1.0
        }

    @staticmethod
    def _load_audio(audio_path: str, target_sr: int = 16000):
        """
        Load any browser-recorded audio (webm, opus, wav, mp4, ogg…) as a
        mono float32 numpy array resampled to target_sr.

        Strategy (in order):
        1. PyAV  — bundles its own codec libs; handles webm/opus natively
                   without a system-level ffmpeg install.
        2. librosa — fallback for wav/mp3/flac when PyAV is unavailable.
        Returns (speech: np.ndarray, sample_rate: int).
        Raises RuntimeError only when both strategies fail.
        """
        # ── Strategy 1: PyAV ────────────────────────────────────────────
        try:
            import av as _av

            frames = []
            with _av.open(audio_path) as container:
                resampler = _av.audio.resampler.AudioResampler(
                    format="fltp",       # float planar
                    layout="mono",
                    rate=target_sr,
                )
                for packet in container.demux(audio=0):
                    for frame in packet.decode():
                        frame.pts = None          # avoid pts discontinuity errors
                        for out in resampler.resample(frame):
                            frames.append(out.to_ndarray()[0])  # shape (N,)

            if frames:
                speech = np.concatenate(frames).astype(np.float32)
                if len(speech) > 0:
                    return speech, target_sr

        except ImportError:
            pass   # av not installed — fall through to librosa
        except Exception as av_err:
            print(f"[EMOTION] PyAV load failed ({type(av_err).__name__}): {av_err} — trying librosa")

        # ── Strategy 2: librosa ─────────────────────────────────────────
        import warnings
        with warnings.catch_warnings():
            warnings.simplefilter("ignore")   # suppress PySoundFile / audioread warnings
            speech, _ = librosa.load(audio_path, sr=target_sr, mono=True)

        return speech, target_sr

    def predict_from_audio(self, audio_path):
        import os, traceback as _tb

        self.eval()
        speech = None

        # ── Stage 1: load audio ──────────────────────────────────────────
        try:
            speech, _ = self._load_audio(audio_path)
        except Exception as load_err:
            print(f"[EMOTION ERROR] Audio load failed: {type(load_err).__name__}: {load_err}")
            _tb.print_exc()
            return self._fallback_result()

        if speech is None or len(speech) == 0:
            print("[EMOTION ERROR] Loaded audio is empty — returning fallback.")
            return self._fallback_result()

        # ── Stage 2: feature extraction ──────────────────────────────────
        try:
            inputs = self.feature_extractor(
                speech,
                sampling_rate=16000,
                return_tensors="pt",
                padding=True,
                return_attention_mask=True,   # always request mask explicitly
            )
        except Exception as feat_err:
            print(f"[EMOTION ERROR] Feature extraction failed: {type(feat_err).__name__}: {feat_err}")
            _tb.print_exc()
            return self._fallback_result()

        # ── Stage 3: model inference ─────────────────────────────────────
        try:
            # Access attention_mask safely — not all extractor versions return it
            attention_mask = inputs.get("attention_mask", None)

            with torch.no_grad():
                logits = self.forward(inputs.input_values, attention_mask)
                probabilities = torch.nn.functional.softmax(logits, dim=-1)

            pred_idx = torch.argmax(probabilities, dim=-1).item()
            confidence = float(probabilities[0][pred_idx].item())

            result = {
                "dominant_tone": self.labels[pred_idx],
                "confidence": confidence,
                "tone_profile": probabilities[0].tolist(),
            }
            print("[EMOTION OUTPUT]", result)
            return result

        except Exception as infer_err:
            print(f"[EMOTION ERROR] Inference failed: {type(infer_err).__name__}: {infer_err}")
            _tb.print_exc()
            return self._fallback_result()