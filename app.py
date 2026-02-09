import streamlit as st
import requests
import hashlib

API_URL = "http://localhost:8000"

st.set_page_config(page_title="MyHR AI", layout="wide")

if "session_id" not in st.session_state:
    st.session_state.session_id = None
if "messages" not in st.session_state:
    st.session_state.messages = []
if "last_audio_url" not in st.session_state:
    st.session_state.last_audio_url = None
if "processed_audio_hash" not in st.session_state:
    st.session_state.processed_audio_hash = None

st.title("MyHR: AI Interviewer")

# --- STEP 1: SETUP ---
if not st.session_state.session_id:
    col1, col2 = st.columns(2)
    with col1:
        jd_text = st.text_area("Job Description", "Software Engineer with Python skills...")
    with col2:
        cv_file = st.file_uploader("Upload CV (PDF)", type=["pdf"])
    
    if st.button("Start Interview", type="primary"):
        if cv_file and jd_text:
            with st.spinner("Initializing Agent..."):
                files = {"cv": cv_file}
                data = {"jd": jd_text}
                try:
                    res = requests.post(f"{API_URL}/start_interview", files=files, data=data)
                    if res.status_code == 200:
                        data = res.json()
                        st.session_state.session_id = data["session_id"]
                        st.session_state.messages.append({"role": "ai", "content": data["question"]})
                        st.session_state.last_audio_url = data.get("audio_url")
                        st.rerun()
                except Exception as e:
                    st.error(f"Connection Error: {e}")

# --- STEP 2: INTERVIEW LOOP ---
else:
    # 1. Display Chat History
    for msg in st.session_state.messages:
        with st.chat_message(msg["role"]):
            st.write(msg["content"])
    
    # 2. Auto-Play AI Audio (Hidden Player)
    if st.session_state.last_audio_url:
        st.audio(st.session_state.last_audio_url, format="audio/mp3", autoplay=True)
    
    st.divider()

    # 3. Microphone Input
    audio_value = st.audio_input("Record your answer")

    if audio_value:
        # FIX: Calculate a hash of the file content to detect new recordings
        audio_bytes = audio_value.getvalue()
        current_hash = hashlib.md5(audio_bytes).hexdigest()
        
        # Only process if this is a NEW recording
        if st.session_state.processed_audio_hash != current_hash:
            st.session_state.processed_audio_hash = current_hash
            
            with st.spinner("Thinking..."):
                # Send to Backend
                files = {"audio": ("answer.wav", audio_value, "audio/wav")}
                data = {"session_id": st.session_state.session_id}
                
                try:
                    res = requests.post(f"{API_URL}/submit_answer", files=files, data=data)
                    if res.status_code == 200:
                        resp = res.json()
                        
                        # Add User's Transcription to Chat
                        st.session_state.messages.append({"role": "user", "content": resp["transcription"]})
                        
                        if resp.get("status") == "completed":
                            st.balloons() # precise celebration
                            st.success("Interview Finished! Generating Final Report...")
        
                            # Render the Markdown Report
                            st.markdown(resp["report"]) 
        
                            # Optional: Add a download button for the report
                            st.download_button(
                                label="Download Report",
                                data=resp["report"],
                                file_name="interview_report.md",
                                mime="text/markdown"
                            )
                        else:
                            # Add AI Response
                            st.session_state.messages.append({"role": "ai", "content": resp["next_question"]})
                            st.session_state.last_audio_url = resp.get("audio_url")
                            
                        st.rerun()
                except Exception as e:
                    st.error(f"Error: {e}")