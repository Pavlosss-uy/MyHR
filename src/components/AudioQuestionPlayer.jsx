import { motion } from "framer-motion";
import { Volume2, VolumeX, RotateCcw } from "lucide-react";
import { Button } from "@/components/ui/button";

/**
 * AudioQuestionPlayer - displays the current question with audio playback controls.
 *
 * @param {Object} props
 * @param {Object} props.question - question object { id, text, category, difficulty }
 * @param {number} props.questionIndex - current question number (0-based)
 * @param {number} props.totalQuestions - total number of questions
 * @param {boolean} props.isPlaying - whether TTS is currently speaking
 * @param {Function} props.onTogglePlay - toggle play/pause
 * @param {Function} props.onReplay - replay the question audio
 */
const AudioQuestionPlayer = ({
    question,
    questionIndex,
    totalQuestions,
    isPlaying,
    onTogglePlay,
    onReplay,
}) => {
    if (!question) return null;

    const categoryColors = {
        Technical: "bg-cobalt/20 text-cobalt-lighter border-cobalt/30",
        Leadership: "bg-purple-500/20 text-purple-300 border-purple-500/30",
        Behavioral: "bg-amber-500/20 text-amber-300 border-amber-500/30",
        "Problem Solving": "bg-mint/20 text-mint border-mint/30",
    };

    const colorClass =
        categoryColors[question.category] ||
        "bg-cobalt/20 text-cobalt-lighter border-cobalt/30";

    return (
        <motion.div
            key={question.id}
            initial={{ opacity: 0, y: 15 }}
            animate={{ opacity: 1, y: 0 }}
            transition={{ duration: 0.5, ease: "easeOut" }}
            className="text-center max-w-2xl mx-auto"
        >
            {/* Question counter + Category */}
            <div className="flex items-center justify-center gap-3 mb-4">
                <span className="text-xs text-cobalt-lighter uppercase tracking-widest font-medium">
                    Question {questionIndex + 1} of {totalQuestions}
                </span>
                <span
                    className={`px-2.5 py-0.5 rounded-full text-[10px] font-semibold uppercase tracking-wider border ${colorClass}`}
                >
                    {question.category}
                </span>
            </div>

            {/* Question text */}
            <h2 className="text-xl lg:text-2xl font-semibold text-primary-foreground/90 leading-relaxed mb-6">
                &ldquo;{question.text}&rdquo;
            </h2>

            {/* Audio controls */}
            <div className="flex items-center justify-center gap-2">
                <Button
                    variant="ghost"
                    size="sm"
                    onClick={onTogglePlay}
                    className={`gap-2 rounded-full px-4 transition-all ${isPlaying
                            ? "bg-cobalt/30 text-cobalt-lighter border border-cobalt/40 shadow-cobalt"
                            : "bg-room-surface text-primary-foreground/60 border border-room-border hover:bg-room-border hover:text-primary-foreground/80"
                        }`}
                >
                    {isPlaying ? (
                        <>
                            <Volume2 className="w-4 h-4 animate-pulse" />
                            <span className="text-xs font-medium">Speaking...</span>
                        </>
                    ) : (
                        <>
                            <Volume2 className="w-4 h-4" />
                            <span className="text-xs font-medium">Play Question</span>
                        </>
                    )}
                </Button>

                <Button
                    variant="ghost"
                    size="icon"
                    onClick={onReplay}
                    className="w-8 h-8 rounded-full bg-room-surface border border-room-border text-primary-foreground/50 hover:bg-room-border hover:text-primary-foreground/70"
                    title="Replay question"
                >
                    <RotateCcw className="w-3.5 h-3.5" />
                </Button>
            </div>
        </motion.div>
    );
};

export default AudioQuestionPlayer;
