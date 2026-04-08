from models.registry import registry

# Pre-load on import so the server is ready immediately
registry.load_emotion_model()

def analyze_voice_tone(audio_path):
    try:
        model = registry.load_emotion_model()
        result = model.predict_from_audio(audio_path)
        
        dominant_tone = result["dominant_tone"]
        
        # Create a formatted tone report
        labels = model.labels
        probs = result["tone_profile"]
        
        tone_report = {}
        for label, prob in zip(labels, probs):
            tone_report[label] = f"{prob * 100:.1f}%"
            
        return dominant_tone, tone_report
    except Exception as e:
        print(f"Error analyzing tone: {e}")
        return "neutral", {"error": str(e)}
