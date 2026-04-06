import { useState, useRef, useCallback } from "react";

/**
 * Custom hook for recording audio from a MediaStream using MediaRecorder.
 * Returns controls and the recorded Blob.
 *
 * @param {MediaStream|null} stream - the media stream from useMediaDevices
 */
export function useAudioRecorder(stream) {
    const [isRecording, setIsRecording] = useState(false);
    const mediaRecorderRef = useRef(null);
    const chunksRef = useRef([]);
    const resolveRef = useRef(null);

    const startRecording = useCallback(() => {
        if (!stream) return;

        chunksRef.current = [];

        // Prefer webm if available, fall back to wav
        const mimeType = MediaRecorder.isTypeSupported("audio/webm;codecs=opus")
            ? "audio/webm;codecs=opus"
            : "audio/wav";

        const recorder = new MediaRecorder(stream, { mimeType });

        recorder.ondataavailable = (e) => {
            if (e.data.size > 0) {
                chunksRef.current.push(e.data);
            }
        };

        recorder.onstop = () => {
            const blob = new Blob(chunksRef.current, { type: "audio/wav" });
            if (resolveRef.current) {
                resolveRef.current(blob);
                resolveRef.current = null;
            }
        };

        mediaRecorderRef.current = recorder;
        recorder.start(250); // collect data every 250ms
        setIsRecording(true);
    }, [stream]);

    const stopRecording = useCallback(() => {
        return new Promise((resolve) => {
            if (
                !mediaRecorderRef.current ||
                mediaRecorderRef.current.state === "inactive"
            ) {
                resolve(null);
                return;
            }

            resolveRef.current = resolve;
            mediaRecorderRef.current.stop();
            setIsRecording(false);
        });
    }, []);

    return {
        isRecording,
        startRecording,
        stopRecording,
    };
}
