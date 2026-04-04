import streamlit as st
import requests
import hashlib
import plotly.graph_objects as go
import streamlit as st

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

st.title("🎙️ MyHR: AI Interviewer")

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
                            # Make sure it grabs the transcription from the final turn!
                            st.session_state.messages.append({"role": "user", "content": resp.get("transcription", "")})
                            st.success("Interview Finished! Report generated.")
                            st.json(resp["report"])
                        else:
                            # Add AI Response
                            st.session_state.messages.append({"role": "ai", "content": resp["next_question"]})
                            st.session_state.last_audio_url = resp.get("audio_url")
                            
                        st.rerun()
                except Exception as e:
                    st.error(f"Error: {e}")
                    
def render_radar_chart(detailed_scores):
    """Generates a Radar Chart for Relevance, Clarity, and Technical Depth."""
    categories = ['Relevance', 'Clarity', 'Technical Depth']
    values = [
        detailed_scores.get('relevance', 0),
        detailed_scores.get('clarity', 0),
        detailed_scores.get('technical_depth', 0)
    ]

    fig = go.Figure()
    fig.add_trace(go.Scatterpolar(
        r=values,
        theta=categories,
        fill='toself',
        name='Candidate Performance',
        line_color='#00d1b2'
    ))

    fig.update_layout(
        polar=dict(radialaxis=dict(visible=True, range=[0, 100])),
        showlegend=False,
        margin=dict(l=20, r=20, t=20, b=20),
        height=300
    )
    return fig

# --- Inside your Main Report Logic ---
def display_final_report(state):
    st.header("📋 Final Interview Analytics")
    
    # 1. Performance Prediction Metric
    # We grab the last prediction stored in the state
    pred_score = state.get("predicted_performance", 5.0)
    
    col1, col2 = st.columns([1, 2])
    
    with col1:
        st.metric(
            label="Predicted Job Performance", 
            value=f"{pred_score} / 10",
            delta="High Potential" if pred_score > 7 else "Needs Training",
            delta_color="normal" if pred_score > 7 else "inverse"
        )
        st.caption("Forecast based on technical depth, consistency, and communication clarity.")

    # 2. Radar Chart for the most recent answer
    with col2:
        if state.get("evaluations"):
            latest_eval = state["evaluations"][-1].get("detailed_scores", {})
            st.subheader("Latest Competency Map")
            st.plotly_chart(render_radar_chart(latest_eval), use_container_width=True)

    # 3. Difficulty Trend
    st.subheader("Interview Adaptive Difficulty")
    diff = state.get("current_difficulty", 3)
    st.progress(diff / 5, text=f"Current Difficulty: Level {diff}")