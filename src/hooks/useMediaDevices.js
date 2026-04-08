import { useState, useEffect, useRef, useCallback } from "react";
import { toast } from "sonner";

/**
 * Custom hook for managing camera and microphone access via getUserMedia.
 * Provides refs/state for video element binding, audio stream for waveform,
 * and toggle controls for camera and microphone.
 */
export function useMediaDevices() {
    const videoRef = useRef(null);
    const [stream, setStream] = useState(null);
    const [audioStream, setAudioStream] = useState(null);
    const [isCameraOn, setIsCameraOn] = useState(true);
    const [isMicOn, setIsMicOn] = useState(true);
    const [error, setError] = useState(null);
    const [permissionState, setPermissionState] = useState("prompt"); // prompt | granted | denied

    // Request media on mount
    useEffect(() => {
        let cancelled = false;

        async function initMedia() {
            try {
                const mediaStream = await navigator.mediaDevices.getUserMedia({
                    video: {
                        width: { ideal: 640 },
                        height: { ideal: 480 },
                        facingMode: "user",
                    },
                    audio: {
                        echoCancellation: true,
                        noiseSuppression: true,
                        autoGainControl: true,
                    },
                });

                if (cancelled) {
                    mediaStream.getTracks().forEach((t) => t.stop());
                    return;
                }

                setStream(mediaStream);
                setAudioStream(mediaStream);
                setPermissionState("granted");
                setError(null);

                // Bind video element
                if (videoRef.current) {
                    videoRef.current.srcObject = mediaStream;
                }
            } catch (err) {
                if (cancelled) return;
                setPermissionState("denied");
                
                let errorMessage = "";
                if (err.name === "NotAllowedError") {
                    errorMessage = "Camera/microphone permission denied. Please click the lock icon in your URL bar to allow access.";
                    toast.error("Permissions Denied", { description: errorMessage });
                } else if (err.name === "NotFoundError") {
                    errorMessage = "No camera or microphone found on this device.";
                    toast.error("Device Not Found", { description: errorMessage });
                } else {
                    errorMessage = `Media error: ${err.message}`;
                    toast.error("Media Error", { description: errorMessage });
                }
                setError(errorMessage);
            }
        }

        initMedia();

        return () => {
            cancelled = true;
        };
    }, []);

    // Cleanup on unmount
    useEffect(() => {
        return () => {
            if (stream) {
                stream.getTracks().forEach((track) => track.stop());
            }
        };
    }, [stream]);

    // Keep video element in sync
    useEffect(() => {
        if (videoRef.current && stream) {
            videoRef.current.srcObject = stream;
        }
    }, [stream]);

    const toggleCamera = useCallback(() => {
        if (!stream) return;
        const videoTracks = stream.getVideoTracks();
        videoTracks.forEach((track) => {
            track.enabled = !track.enabled;
        });
        setIsCameraOn((prev) => !prev);
    }, [stream]);

    const toggleMic = useCallback(() => {
        if (!stream) return;
        const audioTracks = stream.getAudioTracks();
        audioTracks.forEach((track) => {
            track.enabled = !track.enabled;
        });
        setIsMicOn((prev) => !prev);
    }, [stream]);

    return {
        videoRef,
        stream,
        audioStream,
        isCameraOn,
        isMicOn,
        toggleCamera,
        toggleMic,
        error,
        permissionState,
    };
}
