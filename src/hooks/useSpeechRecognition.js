import { useState, useEffect, useRef, useCallback } from "react";

/**
 * Custom hook for real-time speech-to-text using the Web Speech API.
 * Provides a live transcript, final transcript, and controls.
 *
 * @param {Object}  options
 * @param {boolean} options.enabled  – Whether recognition should be active (e.g. mic is on)
 * @param {string}  options.lang     – BCP-47 language tag (default "en-US")
 * @returns {{ transcript: string, interimTranscript: string, isListening: boolean, reset: () => void }}
 */
export function useSpeechRecognition({ enabled = false, lang = "en-US" } = {}) {
    const [transcript, setTranscript] = useState("");          // final, committed text
    const [interimTranscript, setInterimTranscript] = useState(""); // live, tentative text
    const [isListening, setIsListening] = useState(false);
    const recognitionRef = useRef(null);

    // Initialise SpeechRecognition once
    useEffect(() => {
        const SpeechRecognition =
            window.SpeechRecognition || window.webkitSpeechRecognition;

        if (!SpeechRecognition) {
            console.warn("SpeechRecognition API is not supported in this browser.");
            return;
        }

        const recognition = new SpeechRecognition();
        recognition.continuous = true;
        recognition.interimResults = true;
        recognition.lang = lang;

        recognition.onresult = (event) => {
            let interim = "";
            let final = "";
            for (let i = event.resultIndex; i < event.results.length; i++) {
                const result = event.results[i];
                if (result.isFinal) {
                    final += result[0].transcript + " ";
                } else {
                    interim += result[0].transcript;
                }
            }
            if (final) {
                setTranscript((prev) => prev + final);
            }
            setInterimTranscript(interim);
        };

        recognition.onerror = (event) => {
            // "no-speech" and "aborted" are non-fatal — just ignore them
            if (event.error !== "no-speech" && event.error !== "aborted") {
                console.error("SpeechRecognition error:", event.error);
            }
        };

        recognition.onend = () => {
            setIsListening(false);
            // Auto-restart if still enabled (recognition can stop on silence)
            if (recognitionRef.current?._shouldBeRunning) {
                try {
                    recognition.start();
                    setIsListening(true);
                } catch {
                    /* already running */
                }
            }
        };

        recognitionRef.current = recognition;

        return () => {
            recognition.onresult = null;
            recognition.onerror = null;
            recognition.onend = null;
            try {
                recognition.stop();
            } catch {
                /* noop */
            }
        };
    }, [lang]);

    // Start / stop recognition based on `enabled`
    useEffect(() => {
        const recognition = recognitionRef.current;
        if (!recognition) return;

        if (enabled) {
            recognition._shouldBeRunning = true;
            try {
                recognition.start();
                setIsListening(true);
            } catch {
                /* already running */
            }
        } else {
            recognition._shouldBeRunning = false;
            try {
                recognition.stop();
            } catch {
                /* noop */
            }
            setIsListening(false);
            setInterimTranscript("");
        }
    }, [enabled]);

    const reset = useCallback(() => {
        setTranscript("");
        setInterimTranscript("");
    }, []);

    return { transcript, interimTranscript, isListening, reset };
}
