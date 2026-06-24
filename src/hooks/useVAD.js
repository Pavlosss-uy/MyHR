import { useEffect, useRef, useState } from "react";
import { MicVAD, utils } from "@ricky0123/vad-web";

/**
 * Task 5.1 — Silero VAD wrapper using the MicVAD class API (v0.0.22).
 *
 * All assets are served from /public/ (committed to git):
 *   baseAssetPath  "/"  →  /vad.worklet.bundle.min.js + /silero_vad_legacy.onnx
 *   onnxWASMBasePath "/" →  /ort-wasm-simd-threaded*.wasm
 */
export function useVAD() {
    const [vadBlob,      setVadBlob]      = useState(null);
    const [userSpeaking, setUserSpeaking] = useState(false);
    const [listening,    setListening]    = useState(false);
    const [vadError,     setVadError]     = useState(null);
    const vadRef    = useRef(null);
    const pausedRef = useRef(false);

    useEffect(() => {
        let destroyed = false;

        MicVAD.new({
            model: "legacy",
            baseAssetPath:    "/",
            onnxWASMBasePath: "/",
            ortConfig: (ort) => {
                // Single-thread mode: uses ort-wasm-simd.wasm instead of the
                // threaded variant — no SharedArrayBuffer needed.
                ort.env.wasm.numThreads = 1;
            },
            onSpeechStart: () => {
                if (!destroyed && !pausedRef.current) setUserSpeaking(true);
            },
            onSpeechEnd: (audio) => {
                if (destroyed) return;
                setUserSpeaking(false);
                if (pausedRef.current) return;
                try {
                    const wavBuffer = utils.encodeWAV(audio);
                    setVadBlob(new Blob([wavBuffer], { type: "audio/wav" }));
                } catch {
                    // encoding failed — drop silently
                }
            },
            onVADMisfire: () => setUserSpeaking(false),
            positiveSpeechThreshold: 0.80,
            negativeSpeechThreshold: 0.30,
            minSpeechFrames:    3,
            redemptionFrames:   8,
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

    const setVADPaused = (paused) => {
        pausedRef.current = paused;
        if (paused) setUserSpeaking(false);
    };

    return {
        vadBlob,
        clearBlob: () => setVadBlob(null),
        userSpeaking,
        listening,
        vadError,
        setVADPaused,
    };
}
