import { useEffect, useState } from "react";
import { motion, AnimatePresence } from "framer-motion";
import { Camera, CameraOff, AlertCircle, Users, UserX, Eye, ShieldAlert, ShieldCheck } from "lucide-react";

const PROCTOR_ALERTS = {
    multiple:     { icon: Users,  text: "Multiple people detected" },
    no_face:      { icon: UserX,  text: "Face not visible" },
    looking_away: { icon: Eye,    text: "Looking away" },
};

// Tier-based styling (used for both border glow and banner)
const TIER_STYLES = {
    0: { border: "ring-white/5",                    banner: null },
    1: { border: "ring-amber-500/30",               banner: "text-amber-300 bg-amber-500/15 border-amber-500/30" },
    2: { border: "ring-yellow-500/40",               banner: "text-yellow-300 bg-yellow-500/20 border-yellow-500/40" },
    3: { border: "ring-red-500/50 animate-pulse",    banner: "text-red-300 bg-red-500/20 border-red-500/40" },
    4: { border: "ring-red-600/60 animate-pulse",    banner: "text-red-200 bg-red-600/30 border-red-500/50" },
};

// Gaze indicator colors
function gazeIndicatorStyle(gazeScore) {
    if (gazeScore >= 0.7) return "bg-emerald-400 shadow-emerald-400/40";
    if (gazeScore >= 0.4) return "bg-amber-400 shadow-amber-400/40";
    return "bg-red-400 shadow-red-400/40";
}

/**
 * CameraFeed - displays the user's live camera feed with tiered proctoring
 * warnings, gaze quality indicator, and violation counter.
 *
 * @param {Object}          props
 * @param {React.RefObject} props.videoRef       – ref for the <video> element
 * @param {boolean}         props.isCameraOn     – whether camera is active
 * @param {string|null}     props.error          – error message if permission denied
 * @param {string|null}     props.proctorAlert   – "multiple"|"no_face"|"looking_away"|null
 * @param {number}          props.warningTier    – 0-4 escalation tier (default 0)
 * @param {string|null}     props.warningMessage – tier-specific message to display
 * @param {number}          props.gazeScore      – 0.0-1.0 live gaze quality (default 1.0)
 * @param {number}          props.violationCount – total violation count this session (default 0)
 */
const CameraFeed = ({
    videoRef,
    isCameraOn,
    error,
    proctorAlert = null,
    warningTier = 0,
    warningMessage = null,
    gazeScore = 1.0,
    violationCount = 0,
}) => {
    const alert = proctorAlert ? PROCTOR_ALERTS[proctorAlert] : null;
    const tierStyle = TIER_STYLES[warningTier] || TIER_STYLES[0];

    // Auto-dismiss Tier 1 banners after 3 seconds
    const [showTier1, setShowTier1] = useState(true);
    useEffect(() => {
        if (warningTier === 1) {
            setShowTier1(true);
            const t = setTimeout(() => setShowTier1(false), 3000);
            return () => clearTimeout(t);
        }
        setShowTier1(true);
    }, [warningTier, warningMessage]);

    const showBanner = warningTier >= 2 || (warningTier === 1 && showTier1);

    return (
        <motion.div
            initial={{ opacity: 0, scale: 0.95 }}
            animate={{ opacity: 1, scale: 1 }}
            transition={{ duration: 0.5, ease: "easeOut" }}
            className="relative rounded-2xl overflow-hidden bg-room-surface border border-room-border camera-feed-container"
        >
            {/* Live Video */}
            <video
                ref={videoRef}
                autoPlay
                playsInline
                muted
                className={`w-full h-full object-cover transition-opacity duration-300 ${isCameraOn && !error ? "opacity-100" : "opacity-0"
                    }`}
                style={{ transform: "scaleX(-1)" }}
            />

            {/* Camera Off Overlay */}
            {!isCameraOn && !error && (
                <div className="absolute inset-0 flex flex-col items-center justify-center gap-3 bg-room-surface">
                    <div className="w-16 h-16 rounded-full bg-room-border/50 flex items-center justify-center">
                        <CameraOff className="w-7 h-7 text-primary-foreground/40" />
                    </div>
                    <p className="text-sm text-primary-foreground/40 font-medium">
                        Camera is off
                    </p>
                </div>
            )}

            {/* Error Overlay */}
            {error && (
                <div className="absolute inset-0 flex flex-col items-center justify-center gap-3 bg-room-surface p-6">
                    <div className="w-16 h-16 rounded-full bg-destructive/10 flex items-center justify-center">
                        <AlertCircle className="w-7 h-7 text-destructive" />
                    </div>
                    <p className="text-xs text-primary-foreground/50 text-center leading-relaxed max-w-[200px]">
                        {error}
                    </p>
                </div>
            )}

            {/* ── Top-left: Camera status + Gaze indicator ────────────── */}
            {isCameraOn && !error && (
                <div className="absolute top-3 left-3 flex items-center gap-2">
                    <div className="flex items-center gap-1.5 px-2 py-1 rounded-md bg-black/40 backdrop-blur-sm">
                        <Camera className="w-3 h-3 text-mint" />
                        <span className="text-[10px] font-medium text-white/80">LIVE</span>
                    </div>

                    {/* Gaze quality dot */}
                    <div
                        className={`w-2.5 h-2.5 rounded-full transition-colors duration-300 shadow-sm ${gazeIndicatorStyle(gazeScore)}`}
                        title={`Gaze quality: ${Math.round(gazeScore * 100)}%`}
                    />
                </div>
            )}

            {/* ── Top-right: Violation counter (visible at tier 2+) ───── */}
            <AnimatePresence>
                {isCameraOn && !error && warningTier >= 2 && violationCount > 0 && (
                    <motion.div
                        initial={{ opacity: 0, scale: 0.8 }}
                        animate={{ opacity: 1, scale: 1 }}
                        exit={{ opacity: 0, scale: 0.8 }}
                        className="absolute top-3 right-3 flex items-center gap-1.5 px-2.5 py-1 rounded-lg bg-red-500/20 border border-red-500/30 backdrop-blur-sm"
                    >
                        <ShieldAlert className="w-3.5 h-3.5 text-red-400" />
                        <span className="text-[11px] font-bold text-red-300 tabular-nums">
                            {violationCount}
                        </span>
                    </motion.div>
                )}
            </AnimatePresence>

            {/* ── Top-center: Proctor alert type badge ────────────────── */}
            <AnimatePresence>
                {isCameraOn && !error && alert && warningTier >= 1 && (
                    <motion.div
                        initial={{ opacity: 0, y: -8 }}
                        animate={{ opacity: 1, y: 0 }}
                        exit={{ opacity: 0, y: -8 }}
                        transition={{ duration: 0.2 }}
                        className={`absolute top-3 left-1/2 -translate-x-1/2 flex items-center gap-1.5 px-3 py-1.5 rounded-lg border backdrop-blur-sm ${tierStyle.banner}`}
                    >
                        <alert.icon className="w-3.5 h-3.5" />
                        <span className="text-[11px] font-semibold">{alert.text}</span>
                    </motion.div>
                )}
            </AnimatePresence>

            {/* ── Bottom: Escalating warning banner ───────────────────── */}
            <AnimatePresence>
                {isCameraOn && !error && showBanner && warningMessage && (
                    <motion.div
                        initial={{ opacity: 0, y: 8 }}
                        animate={{ opacity: 1, y: 0 }}
                        exit={{ opacity: 0, y: 8 }}
                        transition={{ duration: 0.25 }}
                        className={`absolute bottom-0 inset-x-0 flex items-center gap-2 px-4 py-2.5 backdrop-blur-md border-t ${tierStyle.banner}`}
                    >
                        {warningTier >= 3 ? (
                            <ShieldAlert className="w-4 h-4 shrink-0" />
                        ) : (
                            <AlertCircle className="w-4 h-4 shrink-0" />
                        )}
                        <p className="text-xs font-medium leading-snug">{warningMessage}</p>
                    </motion.div>
                )}
            </AnimatePresence>

            {/* ── Tier 4: Full overlay with pause prompt ──────────────── */}
            <AnimatePresence>
                {isCameraOn && !error && warningTier >= 4 && (
                    <motion.div
                        initial={{ opacity: 0 }}
                        animate={{ opacity: 1 }}
                        exit={{ opacity: 0 }}
                        className="absolute inset-0 bg-black/60 backdrop-blur-sm flex flex-col items-center justify-center gap-3 z-10"
                    >
                        <div className="w-14 h-14 rounded-full bg-red-500/20 flex items-center justify-center">
                            <ShieldAlert className="w-7 h-7 text-red-400" />
                        </div>
                        <p className="text-sm font-bold text-red-300 text-center px-6">
                            Interview Integrity Alert
                        </p>
                        <p className="text-xs text-red-200/70 text-center px-8 max-w-[280px]">
                            {warningMessage || "Please remain focused on the interview."}
                        </p>
                    </motion.div>
                )}
            </AnimatePresence>

            {/* ── Integrity-OK badge (bottom-right, only when clean) ──── */}
            {isCameraOn && !error && warningTier === 0 && violationCount === 0 && (
                <div className="absolute bottom-3 right-3 flex items-center gap-1 px-2 py-1 rounded-md bg-black/30 backdrop-blur-sm">
                    <ShieldCheck className="w-3 h-3 text-emerald-400" />
                    <span className="text-[9px] font-medium text-emerald-300/80">OK</span>
                </div>
            )}

            {/* Border glow (tier-aware) */}
            {isCameraOn && !error && (
                <div className={`absolute inset-0 rounded-2xl ring-1 ring-inset pointer-events-none transition-all duration-500 ${tierStyle.border}`} />
            )}
        </motion.div>
    );
};

export default CameraFeed;
