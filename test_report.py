import os
from dotenv import load_dotenv

# 1. Load environment variables (API Keys)
load_dotenv()

# 2. Import your generator function
try:
    from services import generate_final_markdown_report
except ImportError:
    print("❌ Error: Could not import 'generate_final_markdown_report'.")
    print("Make sure you are running this script from the 'GP code' folder.")
    exit()

# 3. Create Dummy Interview Data (Mocking the state)
mock_candidate_name = "Test Candidate John"
mock_job_description = "We need a Senior Python Engineer with RAG experience."

mock_evaluations = [
    {
        "question": "Tell me about your experience with Python.",
        "answer": "I have used Python for 5 years, mostly with Django and Flask.",
        "score": 78,
        "feedback": "Good experience but lacked details on async.",
        "tone": "Neutral",
        "tone_details": {"neu": "72.3%", "hap": "15.1%", "ang": "2.4%", "sad": "10.2%"}
    },
    {
        "question": "How do you handle memory leaks?",
        "answer": "I don't really know, I just restart the server.",
        "score": 15,
        "feedback": "Poor answer. Restarting is not a fix.",
        "tone": "Sad",
        "tone_details": {"neu": "20.1%", "hap": "5.3%", "ang": "8.9%", "sad": "65.7%"}
    },
    {
        "question": "Explain RAG architecture.",
        "answer": "Retrieval Augmented Generation uses a vector DB to fetch context.",
        "score": 88,
        "feedback": "Excellent and concise definition.",
        "tone": "Happy",
        "tone_details": {"neu": "30.5%", "hap": "55.2%", "ang": "1.1%", "sad": "13.2%"}
    }
]

mock_tone_analysis = {
    "primary_emotion": "Neutral",
    "full_analysis": "The candidate showed varied emotional responses across the interview."
}

print("🚀 Generating Report... Please wait.")

# 4. Call the function directly
try:
    report = generate_final_markdown_report(
        mock_candidate_name,
        mock_job_description,
        mock_evaluations,
        mock_tone_analysis
    )
    
    print("\n" + "="*40)
    print("       🎉 FINAL REPORT OUTPUT       ")
    print("="*40 + "\n")
    print(report)
    print("\n" + "="*40)

except Exception as e:
    print(f"💥 Crash: {e}")