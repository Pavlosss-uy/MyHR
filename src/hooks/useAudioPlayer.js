import { useState, useCallback, useEffect, useRef } from "react";

/**
 * Custom hook for text-to-speech playback of interview questions
 * using the browser's SpeechSynthesis API.
 */
export function useAudioPlayer() {
    const [isPlaying, setIsPlaying] = useState(false);
    const [isSupported, setIsSupported] = useState(true);
    const utteranceRef = useRef(null);

    useEffect(() => {
        if (!window.speechSynthesis) {
            setIsSupported(false);
        }
        return () => {
            // Cancel any ongoing speech on unmount
            if (window.speechSynthesis) {
                window.speechSynthesis.cancel();
            }
        };
    }, []);

    const speakQuestion = useCallback(
        (text) => {
            if (!isSupported || !text) return;

            // Cancel any current speech
            window.speechSynthesis.cancel();

            const utterance = new SpeechSynthesisUtterance(text);
            utterance.rate = 0.95;
            utterance.pitch = 1;
            utterance.volume = 1;

            // Try to pick a natural-sounding English voice
            const voices = window.speechSynthesis.getVoices();
            const preferred = voices.find(
                (v) =>
                    v.lang.startsWith("en") &&
                    (v.name.includes("Google") ||
                        v.name.includes("Natural") ||
                        v.name.includes("Microsoft"))
            );
            if (preferred) {
                utterance.voice = preferred;
            } else {
                const english = voices.find((v) => v.lang.startsWith("en"));
                if (english) utterance.voice = english;
            }

            utterance.onstart = () => setIsPlaying(true);
            utterance.onend = () => setIsPlaying(false);
            utterance.onerror = () => setIsPlaying(false);

            utteranceRef.current = utterance;
            window.speechSynthesis.speak(utterance);
        },
        [isSupported]
    );

    const stopSpeaking = useCallback(() => {
        if (window.speechSynthesis) {
            window.speechSynthesis.cancel();
        }
        setIsPlaying(false);
    }, []);

    const toggleSpeaking = useCallback(
        (text) => {
            if (isPlaying) {
                stopSpeaking();
            } else {
                speakQuestion(text);
            }
        },
        [isPlaying, speakQuestion, stopSpeaking]
    );

    return {
        isPlaying,
        isSupported,
        speakQuestion,
        stopSpeaking,
        toggleSpeaking,
    };
}
