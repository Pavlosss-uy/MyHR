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
if "interview_completed" not in st.session_state:
    st.session_state.interview_completed = False
if "final_report" not in st.session_state:
    st.session_state.final_report = None

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
    # Show final report if interview is done
    if st.session_state.get("interview_completed") and st.session_state.get("final_report"):
        st.success("Interview Complete! Report generated.")
        for msg in st.session_state.messages:
            with st.chat_message(msg["role"]):
                st.write(msg["content"])
        display_final_report(st.session_state.final_report)
        st.stop()

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
                        
                        if resp.get("status") == "completed":
                            # Append transcription once only
                            st.session_state.messages.append({"role": "user", "content": resp.get("transcription", "")})
                            st.session_state.interview_completed = True
                            st.session_state.final_report = {
                                "predicted_performance": resp["report"][-1].get("predicted_job_performance", 5.0) if resp.get("report") else 5.0,
                                "evaluations": resp.get("report", []),
                                "current_difficulty": 3
                            }
                        else:
                            # Add User's Transcription to Chat
                            st.session_state.messages.append({"role": "user", "content": resp["transcription"]})
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

def create_shap_waterfall(shap_values, features, feature_names=None):
    """Creates a Plotly horizontal waterfall-style bar chart for SHAP values."""
    if feature_names is None:
        feature_names = [
            "skill_match", "relevance", "clarity", "depth",
            "confidence", "consistency", "gaps_inverted", "experience"
        ]

    # Support nested lists like [[...]]
    if isinstance(shap_values, list) and len(shap_values) > 0 and isinstance(shap_values[0], list):
        shap_values = shap_values[0]

    if isinstance(features, list) and len(features) > 0 and isinstance(features[0], list):
        features = features[0]

    labels = [
        f"{name} ({round(value, 3)})"
        for name, value in zip(feature_names, features)
    ]

    colors = ["green" if v >= 0 else "red" for v in shap_values]

    fig = go.Figure(
        go.Bar(
            x=shap_values,
            y=labels,
            orientation="h",
            marker_color=colors,
            text=[f"{v:+.3f}" for v in shap_values],
            textposition="outside",
            hovertemplate="Feature: %{y}<br>SHAP: %{x:.4f}<extra></extra>"
        )
    )

    fig.update_layout(
        title="Feature Contribution to Predicted Score",
        xaxis_title="SHAP Contribution",
        yaxis_title="Features",
        height=420,
        margin=dict(l=20, r=20, t=50, b=20)
    )

    return fig

# --- Inside your Main Report Logic ---
def display_final_report(state):
    st.header("📋 Final Interview Analytics")

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

    with col2:
        if state.get("evaluations"):
            latest_eval = state["evaluations"][-1]
            latest_scores = latest_eval.get("detailed_scores", {})
            st.subheader("Latest Competency Map")
            st.plotly_chart(render_radar_chart(latest_scores), use_container_width=True)

            # After radar chart
            shap_values = latest_eval.get("shap_values")
            feature_values = latest_eval.get("feature_values")

            if shap_values and feature_values:
                st.subheader("Score Explanation")
                fig = create_shap_waterfall(shap_values, feature_values)
                st.plotly_chart(fig, use_container_width=True)
                st.caption("Green bars pushed the score UP. Red bars pushed it DOWN.")
            else:
                st.info("SHAP explanation not available for this evaluation.")

    st.subheader("Interview Adaptive Difficulty")
    diff = state.get("current_difficulty", 3)
    st.progress(diff / 5, text=f"Current Difficulty: Level {diff}")

    if state.get("evaluations"):
        st.subheader("Latest Answer Feedback")
        latest_eval = state["evaluations"][-1]
        st.write(f"**Question:** {latest_eval.get('question', '')}")
        st.write(f"**Answer:** {latest_eval.get('answer', '')}")
        st.write(f"**Feedback:** {latest_eval.get('feedback', '')}")