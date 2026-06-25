# MyHR backend (FastAPI) — Task 7.1
#
# Base: python:3.12-slim. The plan specified 3.11, but the dev machine runs 3.14
# (no TensorFlow wheel → DeepFace dropped, OpenCV/YuNet proctoring used instead).
# 3.12 is the sweet spot: modern, and the full proctoring/audio/ML stack installs
# cleanly. The image deliberately does NOT include TensorFlow/DeepFace.
FROM python:3.12-slim

ENV PYTHONUNBUFFERED=1 \
    PYTHONDONTWRITEBYTECODE=1 \
    PIP_NO_CACHE_DIR=1

# System libraries needed by:
#   opencv-python-headless → libglib2.0-0
#   librosa / soundfile     → libsndfile1
#   av (PyAV) / audio decode → ffmpeg
RUN apt-get update && apt-get install -y --no-install-recommends \
        libglib2.0-0 \
        libsndfile1 \
        ffmpeg \
    && rm -rf /var/lib/apt/lists/*

WORKDIR /app

# Install Python deps first for better layer caching.
COPY requirements.txt .
RUN pip install --upgrade pip && pip install -r requirements.txt

# spaCy model used by Presidio PII redaction (Task 5.2).
RUN python -m spacy download en_core_web_lg || true

# Copy the application source. Large model checkpoints are excluded via
# .dockerignore and mounted at runtime (see docker-compose.yml).
COPY . .

EXPOSE 8000

# Proctor (OpenCV/YuNet) warms up on FastAPI startup; no model download needed.
CMD ["uvicorn", "server:app", "--host", "0.0.0.0", "--port", "8000"]
