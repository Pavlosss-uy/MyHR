const API_BASE = "/api";

/**
 * Start an interview session.
 * @param {File} cvFile - PDF CV file
 * @param {string} jdText - Job description text
 * @returns {{ session_id: string, question: string, audio_url: string|null }}
 */
export async function startInterview(cvFile, jdText) {
    const form = new FormData();
    form.append("cv", cvFile);
    form.append("jd", jdText);

    const res = await fetch(`${API_BASE}/start_interview`, {
        method: "POST",
        body: form,
    });

    if (!res.ok) {
        const err = await res.text();
        throw new Error(`Start interview failed: ${err}`);
    }

    return res.json();
}

/**
 * Submit a recorded audio answer.
 * @param {string} sessionId
 * @param {Blob} audioBlob - WAV audio blob
 * @returns {{ status: string, transcription: string, next_question?: string, audio_url?: string, feedback?: object, report?: Array }}
 */
export async function submitAnswer(sessionId, audioBlob) {
    const form = new FormData();
    form.append("session_id", sessionId);
    form.append("audio", audioBlob, "answer.wav");

    const res = await fetch(`${API_BASE}/submit_answer`, {
        method: "POST",
        body: form,
    });

    if (!res.ok) {
        const err = await res.text();
        throw new Error(`Submit answer failed: ${err}`);
    }

    return res.json();
}

/**
 * Fetch the final interview report.
 * @param {string} sessionId
 * @returns {{ session_id, evaluations, average_score, total_questions, job_title, candidate_name }}
 */
export async function getReport(sessionId) {
    const res = await fetch(`${API_BASE}/end_interview/${sessionId}`);

    if (!res.ok) {
        const err = await res.text();
        throw new Error(`Get report failed: ${err}`);
    }

    return res.json();
}
