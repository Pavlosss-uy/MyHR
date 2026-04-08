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
        if (!stream) {
            console.error("AudioRecorder: No stream available");
            return;
        }

        chunksRef.current = [];

        try {
            let options = {};
            if (MediaRecorder.isTypeSupported("audio/webm;codecs=opus")) {
                options.mimeType = "audio/webm;codecs=opus";
            } else if (MediaRecorder.isTypeSupported("audio/mp4")) {
                options.mimeType = "audio/mp4";
            }
            // If neither is supported, leave options empty to let the browser pick its default.

            const recorder = new MediaRecorder(stream, options);

            recorder.ondataavailable = (e) => {
                if (e.data.size > 0) {
                    chunksRef.current.push(e.data);
                }
            };

            recorder.onstop = () => {
                const blob = new Blob(chunksRef.current, { type: recorder.mimeType || "audio/webm" });
                if (resolveRef.current) {
                    resolveRef.current(blob);
                    resolveRef.current = null;
                }
            };

            mediaRecorderRef.current = recorder;
            recorder.start(250); // collect data every 250ms
            setIsRecording(true);
        } catch (err) {
            console.error("Failed to start MediaRecorder:", err);
            // We use standard error throwing here, the caller can catch or we just rely on console
        }
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
