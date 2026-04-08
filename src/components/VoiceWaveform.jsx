import { useEffect, useState, useRef } from "react";

/**
 * VoiceWaveform - animated bar visualization.
 * When an audioStream (MediaStream) is provided, uses Web Audio API AnalyserNode
 * to render real microphone data. Otherwise falls back to random animation.
 *
 * @param {Object} props
 * @param {boolean} props.isActive - whether the waveform should animate
 * @param {MediaStream|null} props.audioStream - optional real audio stream
 */
const VoiceWaveform = ({ isActive = true, audioStream = null }) => {
    const BAR_COUNT = 40;
    const [bars, setBars] = useState(Array(BAR_COUNT).fill(0.3));
    const analyserRef = useRef(null);
    const audioCtxRef = useRef(null);
    const sourceRef = useRef(null);
    const rafRef = useRef(null);

    // Real audio analysis
    useEffect(() => {
        if (!audioStream || !isActive) {
            // Cleanup if stream goes away
            if (audioCtxRef.current) {
                audioCtxRef.current.close().catch(() => { });
                audioCtxRef.current = null;
                analyserRef.current = null;
                sourceRef.current = null;
            }
            if (rafRef.current) {
                cancelAnimationFrame(rafRef.current);
                rafRef.current = null;
            }
            return;
        }

        try {
            const audioCtx = new (window.AudioContext || window.webkitAudioContext)();
            const analyser = audioCtx.createAnalyser();
            analyser.fftSize = 128;
            analyser.smoothingTimeConstant = 0.7;

            const source = audioCtx.createMediaStreamSource(audioStream);
            source.connect(analyser);

            audioCtxRef.current = audioCtx;
            analyserRef.current = analyser;
            sourceRef.current = source;

            const dataArray = new Uint8Array(analyser.frequencyBinCount);

            const tick = () => {
                analyser.getByteFrequencyData(dataArray);

                const newBars = Array(BAR_COUNT)
                    .fill(0)
                    .map((_, i) => {
                        const dataIndex = Math.floor(
                            (i / BAR_COUNT) * dataArray.length
                        );
                        return Math.max(0.08, dataArray[dataIndex] / 255);
                    });

                setBars(newBars);
                rafRef.current = requestAnimationFrame(tick);
            };

            tick();
        } catch {
            // fall through to random animation
        }

        return () => {
            if (rafRef.current) cancelAnimationFrame(rafRef.current);
            if (audioCtxRef.current) {
                audioCtxRef.current.close().catch(() => { });
            }
        };
    }, [audioStream, isActive]);

    // Reset to flat bars when inactive or no stream
    useEffect(() => {
        if (audioStream && isActive) return;
        setBars(Array(BAR_COUNT).fill(0.08));
    }, [isActive, audioStream]);

    return (
        <div className="flex items-center justify-center gap-[3px] h-32">
            {bars.map((height, i) => {
                const distFromCenter = Math.abs(i - (BAR_COUNT - 1) / 2) / ((BAR_COUNT - 1) / 2);
                const maxScale = 1 - distFromCenter * 0.5;
                const barHeight = height * maxScale;

                return (
                    <div
                        key={i}
                        className="w-[4px] rounded-full transition-all duration-100 ease-out"
                        style={{
                            height: `${barHeight * 100}%`,
                            background: `linear-gradient(180deg, 
                hsl(160 60% 55% / ${0.6 + barHeight * 0.4}) 0%, 
                hsl(222 64% 50% / ${0.4 + barHeight * 0.6}) 50%,
                hsl(222 64% 33% / ${0.3 + barHeight * 0.7}) 100%)`,
                            boxShadow: isActive
                                ? `0 0 ${8 + barHeight * 12}px hsl(160 60% 45% / ${barHeight * 0.4})`
                                : "none",
                        }}
                    />
                );
            })}
        </div>
    );
};

export default VoiceWaveform;
