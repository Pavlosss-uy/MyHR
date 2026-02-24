import { motion } from "framer-motion";
import { Camera, CameraOff, AlertCircle } from "lucide-react";

/**
 * CameraFeed - displays the user's live camera feed with graceful fallback states.
 *
 * @param {Object} props
 * @param {React.RefObject} props.videoRef - ref for the <video> element
 * @param {boolean} props.isCameraOn - whether camera is active
 * @param {string|null} props.error - error message if permission denied
 */
const CameraFeed = ({ videoRef, isCameraOn, error }) => {
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

            {/* Camera Active Indicator */}
            {isCameraOn && !error && (
                <div className="absolute top-3 left-3 flex items-center gap-1.5 px-2 py-1 rounded-md bg-black/40 backdrop-blur-sm">
                    <Camera className="w-3 h-3 text-mint" />
                    <span className="text-[10px] font-medium text-white/80">LIVE</span>
                </div>
            )}

            {/* Subtle border glow */}
            {isCameraOn && !error && (
                <div className="absolute inset-0 rounded-2xl ring-1 ring-inset ring-white/5 pointer-events-none" />
            )}
        </motion.div>
    );
};

export default CameraFeed;
