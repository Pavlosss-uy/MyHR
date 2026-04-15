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

    // Preload voices on mount so getVoices() is populated on first call
    useEffect(() => {
        if (!window.speechSynthesis) return;
        const load = () => window.speechSynthesis.getVoices();
        load();
        window.speechSynthesis.addEventListener("voiceschanged", load);
        return () => window.speechSynthesis.removeEventListener("voiceschanged", load);
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

            // Force a female English voice — no male fallback
            const voices = window.speechSynthesis.getVoices();

            // Explicit female voice names (Chrome, Edge, Safari, Firefox)
            const FEMALE_VOICE_NAMES = [
                "Google UK English Female",
                "Google US English",          // female on most platforms
                "Microsoft Zira",             // Windows female
                "Microsoft Jenny",            // Windows female (newer)
                "Microsoft Aria",             // Edge female
                "Samantha",                   // macOS/iOS female
                "Karen",                      // macOS female
                "Moira",                      // macOS female
                "Tessa",                      // macOS female
                "Fiona",                      // macOS female
            ];

            const MALE_VOICE_NAMES = ["David", "Mark", "Daniel", "Alex", "Fred", "Bruce", "Albert"];

            const isFemale = (v) => {
                const n = v.name;
                if (MALE_VOICE_NAMES.some((m) => n.includes(m))) return false;
                if (FEMALE_VOICE_NAMES.some((f) => n === f || n.includes(f))) return true;
                // Heuristic: name contains "Female" or common female identifiers
                return /female|woman|girl/i.test(n);
            };

            // Priority 1: exact known female name
            let picked = voices.find((v) => v.lang.startsWith("en") && FEMALE_VOICE_NAMES.includes(v.name));
            // Priority 2: any heuristically female English voice
            if (!picked) picked = voices.find((v) => v.lang.startsWith("en") && isFemale(v));
            // Priority 3: any English voice that isn't in the male list
            if (!picked) picked = voices.find((v) => v.lang.startsWith("en") && !MALE_VOICE_NAMES.some((m) => v.name.includes(m)));

            // Raise pitch slightly if we couldn't guarantee a female voice, to reduce male-sounding output
            if (!picked) {
                utterance.pitch = 1.2;
            } else {
                utterance.voice = picked;
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
