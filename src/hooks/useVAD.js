import { useEffect, useRef, useState } from "react";
import { MicVAD, utils } from "@ricky0123/vad-web";

/**
 * Task 5.1 — Silero VAD wrapper using the MicVAD class API (v0.0.22).
 *
 * All assets are served from /public/ (committed to git):
 *   baseAssetPath  "/"  →  /vad.worklet.bundle.min.js + /silero_vad_legacy.onnx
 *   onnxWASMBasePath "/" →  /ort-wasm-simd-threaded*.wasm
 *
 * stream (optional): pass the existing MediaStream from useMediaDevices so the
 * VAD reuses the already-granted mic instead of calling getUserMedia again.
 * Dual concurrent getUserMedia calls on Windows can cause the second one to
 * fail silently, breaking silence detection entirely.
 */
export function useVAD({ onSpeechStart: onSpeechStartCb, stream: providedStream } = {}) {
    const [vadBlob,      setVadBlob]      = useState(null);
    const [userSpeaking, setUserSpeaking] = useState(false);
    const [listening,    setListening]    = useState(false);
    const [vadError,     setVadError]     = useState(null);
    const vadRef    = useRef(null);
    const pausedRef = useRef(false);
    // Stable ref so the MicVAD closure always calls the latest callback
    const cbRef = useRef(onSpeechStartCb);
    cbRef.current = onSpeechStartCb;

    useEffect(() => {
        // If a stream is expected (non-undefined) but not yet ready, wait for
        // the next render when useMediaDevices resolves getUserMedia.
        if (providedStream === null) return;

        let destroyed = false;

        // Extract audio-only tracks from the provided stream so MicVAD doesn't
        // choke on video tracks. Fall back to requesting its own mic if none given.
        let streamOption = {};
        if (providedStream) {
            const audioTracks = providedStream.getAudioTracks();
            if (audioTracks.length > 0) {
                streamOption = { stream: new MediaStream(audioTracks) };
            }
        }

        MicVAD.new({
            model: "legacy",
            baseAssetPath:    "/",
            onnxWASMBasePath: "/",
            ortConfig: (ort) => {
                // Single-thread mode: uses ort-wasm-simd.wasm instead of the
                // threaded variant — no SharedArrayBuffer needed.
                ort.env.wasm.numThreads = 1;
            },
            ...streamOption,
            onSpeechStart: () => {
                if (destroyed || pausedRef.current) return;
                setUserSpeaking(true);
                cbRef.current?.();
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
            positiveSpeechThreshold: 0.65,
            negativeSpeechThreshold: 0.30,
            minSpeechFrames:    3,
            redemptionFrames:   20,
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
    }, [providedStream]);

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
