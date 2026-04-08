import { useState, useRef, useCallback } from "react";

export function useAudioRecorder(stream) {
    const [isRecording, setIsRecording] = useState(false);
    const mediaRecorderRef = useRef(null);
    const chunksRef = useRef([]);
    const resolveRef = useRef(null);
    const localStreamRef = useRef(null);

    // Throws on permission denial or MediaRecorder failure so the caller can show feedback.
    const startRecording = useCallback(async () => {
        let activeStream = stream;

        // No stream from useMediaDevices — request audio permission now.
        if (!activeStream) {
            activeStream = await navigator.mediaDevices.getUserMedia({
                audio: {
                    echoCancellation: true,
                    noiseSuppression: true,
                    autoGainControl: true,
                },
            });
            localStreamRef.current = activeStream;
        }

        chunksRef.current = [];

        let options = {};
        if (MediaRecorder.isTypeSupported("audio/webm;codecs=opus")) {
            options.mimeType = "audio/webm;codecs=opus";
        } else if (MediaRecorder.isTypeSupported("audio/mp4")) {
            options.mimeType = "audio/mp4";
        }

        // Use audio-only stream to avoid video tracks conflicting with audio MIME type
        const audioTracks = activeStream.getAudioTracks();
        const audioOnlyStream = audioTracks.length > 0
            ? new MediaStream(audioTracks)
            : activeStream;

        const recorder = new MediaRecorder(audioOnlyStream, options);

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
            if (localStreamRef.current) {
                localStreamRef.current.getTracks().forEach((t) => t.stop());
                localStreamRef.current = null;
            }
        };

        mediaRecorderRef.current = recorder;
        recorder.start(250);
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
