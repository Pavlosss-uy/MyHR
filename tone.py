import traceback
from models.registry import registry

# Pre-load on import so the server is ready immediately
registry.load_emotion_model()

_FALLBACK_TONE = "neutral"
_FALLBACK_REPORT = {
    "neutral": "100.0%",
    "confident": "0.0%",
    "hesitant": "0.0%",
    "nervous": "0.0%",
    "engaged": "0.0%",
    "frustrated": "0.0%",
    "enthusiastic": "0.0%",
    "uncertain": "0.0%",
    "_fallback": "true",
}


def analyze_voice_tone(audio_path: str):
    """
    Run the emotion model on an audio file.
    ALWAYS returns (dominant_tone: str, tone_report: dict).
    Never raises — returns fallback on any failure.
    """
    try:
        model = registry.load_emotion_model()
        result = model.predict_from_audio(audio_path)

        dominant_tone = result["dominant_tone"]
        labels = model.labels
        probs = result["tone_profile"]

        tone_report = {label: f"{prob * 100:.1f}%" for label, prob in zip(labels, probs)}

        emotion_result = {
            "primary_emotion": dominant_tone,
            "full_analysis": tone_report,
            "confidence": result.get("confidence", 0.5),
        }
        print("[EMOTION OUTPUT]", emotion_result)
        return dominant_tone, tone_report

    except Exception as e:
        print(f"[EMOTION ERROR] analyze_voice_tone failed: {type(e).__name__}: {e}")
        traceback.print_exc()
        return _FALLBACK_TONE, _FALLBACK_REPORT
