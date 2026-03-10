from deepface import DeepFace
import os

def analyze_emotion(image_path: str):
    """
    Analyzes the dominant emotion in the given image using DeepFace.
    """
    if not os.path.exists(image_path):
        return {"error": "Image file not found"}
        
    try:
        # DeepFace.analyze returns a list of dicts (one for each face detected)
        # We assume single face for this interview context
        result = DeepFace.analyze(
            img_path=image_path, 
            actions=['emotion'],
            enforce_detection=False # Don't crash if no face found, just may verify result
        )
        
        # It usually returns a list
        if isinstance(result, list):
            result = result[0]
            
        return {
            "dominant_emotion": result['dominant_emotion'],
            "emotion_scores": result['emotion']
        }
    except Exception as e:
        return {"error": str(e)}

if __name__ == "__main__":
    print("--- Testing Vision Module ---")
    # Need a dummy image to test. 
    # User can place an image at 'test_face.jpg' to test.
    test_img = "test_face.jpg"
    if os.path.exists(test_img):
        print(analyze_emotion(test_img))
    else:
        print(f"Please place a file named '{test_img}' to test.")
