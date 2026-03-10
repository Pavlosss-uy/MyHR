// Mock Interview API Service
// Simulates backend endpoints for interview data

const MOCK_DELAY = 600; // ms

const mockQuestions = [
    {
        id: "q1",
        text: "Tell me about your experience leading cross-functional engineering teams.",
        category: "Leadership",
        difficulty: "medium",
        timeLimit: 120,
    },
    {
        id: "q2",
        text: "How do you approach system design for scalable applications?",
        category: "Technical",
        difficulty: "hard",
        timeLimit: 180,
    },
    {
        id: "q3",
        text: "Describe a challenging technical decision you've made recently and how you arrived at it.",
        category: "Problem Solving",
        difficulty: "medium",
        timeLimit: 150,
    },
    {
        id: "q4",
        text: "How do you handle conflict within your team, especially during high-pressure deadlines?",
        category: "Behavioral",
        difficulty: "medium",
        timeLimit: 120,
    },
    {
        id: "q5",
        text: "Walk me through how you would optimize a slow database query in a production system.",
        category: "Technical",
        difficulty: "hard",
        timeLimit: 180,
    },
];

const mockSession = {
    id: "session-001",
    jobTitle: "Senior Software Engineer",
    company: "IntervAI",
    duration: 30, // minutes
    totalQuestions: mockQuestions.length,
    status: "in_progress",
};

/**
 * Simulates a network delay
 */
const delay = (ms = MOCK_DELAY) =>
    new Promise((resolve) => setTimeout(resolve, ms));

/**
 * Fetch interview questions from the "backend"
 * @returns {Promise<Array>} list of interview questions
 */
export async function fetchInterviewQuestions() {
    await delay();
    return {
        success: true,
        data: mockQuestions,
    };
}

/**
 * Fetch the current interview session config
 * @returns {Promise<Object>} session metadata
 */
export async function fetchInterviewSession() {
    await delay(400);
    return {
        success: true,
        data: mockSession,
    };
}

/**
 * Submit a recorded answer for a question
 * @param {string} questionId
 * @param {Blob|null} audioBlob - the recorded audio (simulated)
 * @returns {Promise<Object>} submission result
 */
export async function submitAnswer(questionId, audioBlob) {
    await delay(800);
    return {
        success: true,
        data: {
            questionId,
            receivedAt: new Date().toISOString(),
            audioSize: audioBlob ? audioBlob.size : 0,
            status: "received",
        },
    };
}

/**
 * End the interview session
 * @returns {Promise<Object>} session end result
 */
export async function endInterviewSession() {
    await delay(500);
    return {
        success: true,
        data: {
            sessionId: mockSession.id,
            endedAt: new Date().toISOString(),
            status: "completed",
            redirectTo: "/feedback",
        },
    };
}
