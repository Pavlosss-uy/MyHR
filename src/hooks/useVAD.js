import { useEffect, useRef, useState } from "react";
import { MicVAD, utils } from "@ricky0123/vad-web";

/**
 * Task 5.1 — Silero VAD wrapper using the MicVAD class API.
 *
 * WASM / model files must be served from /public/:
 *   /vad.worklet.bundle.min.js
 *   /silero_vad_v5.onnx
 *   /ort-wasm-simd-threaded*.wasm
 */
export function useVAD() {
    const [vadBlob,      setVadBlob]     = useState(null);
    const [userSpeaking, setUserSpeaking] = useState(false);
    const [listening,    setListening]   = useState(false);
    const [vadError,     setVadError]    = useState(null);
    const vadRef     = useRef(null);
    const pausedRef  = useRef(false); // external pause flag (set by caller)

    useEffect(() => {
        let destroyed = false;

        MicVAD.new({
            onSpeechStart: () => {
                if (!destroyed && !pausedRef.current) setUserSpeaking(true);
            },
            onSpeechEnd: (audio) => {
                if (destroyed) return;
                setUserSpeaking(false);
                // Discard capture if the caller has paused VAD (e.g. TTS playing)
                if (pausedRef.current) return;
                try {
                    const wavBuffer = utils.encodeWAV(audio);
                    setVadBlob(new Blob([wavBuffer], { type: "audio/wav" }));
                } catch {
                    // encoding failed — drop silently
                }
            },
            workletURL: "/vad.worklet.bundle.min.js",
            modelURL:   "/silero_vad_v5.onnx",
            ortConfig: (ort) => {
                ort.env.wasm.wasmPaths = "/";
            },
            positiveSpeechThreshold: 0.80,
            negativeSpeechThreshold: 0.30,
            minSpeechFrames:   3,
            redemptionFrames:  8,
            preSpeechPadFrames: 2,
        })
            .then((vad) => {
                if (destroyed) { vad.destroy(); return; }
                vadRef.current = vad;
                vad.start();
                setListening(true);
            })
            .catch((err) => {
                if (!destroyed) setVadError(err?.message ?? String(err));
            });

        return () => {
            destroyed = true;
            setListening(false);
            if (vadRef.current) {
                vadRef.current.destroy();
                vadRef.current = null;
            }
        };
    }, []);

    /**
     * Soft-pause: keep the MicVAD running (avoids re-init latency) but
     * discard any speech segments captured while paused. Call with
     * `true` while TTS is playing, `false` when it ends.
     */
    const setVADPaused = (paused) => {
        pausedRef.current = paused;
        if (paused) setUserSpeaking(false);
    };

    return {
        vadBlob,
        clearBlob:    () => setVadBlob(null),
        userSpeaking,
        listening,
        vadError,
        setVADPaused,
    };
}
