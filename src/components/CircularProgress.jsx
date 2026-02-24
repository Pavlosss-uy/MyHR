import { cn } from "@/lib/utils";

const colorMap = {
    cobalt: "stroke-cobalt",
    mint: "stroke-mint",
    warning: "stroke-warning",
};

const CircularProgress = ({
    value,
    size = 120,
    strokeWidth = 8,
    label,
    sublabel,
    className,
    color = "cobalt",
}) => {
    const radius = (size - strokeWidth) / 2;
    const circumference = 2 * Math.PI * radius;
    const offset = circumference - (value / 100) * circumference;

    return (
        <div className={cn("flex flex-col items-center gap-2", className)}>
            <div className="relative" style={{ width: size, height: size }}>
                <svg width={size} height={size} className="-rotate-90">
                    <circle
                        cx={size / 2}
                        cy={size / 2}
                        r={radius}
                        fill="none"
                        stroke="hsl(var(--muted))"
                        strokeWidth={strokeWidth}
                    />
                    <circle
                        cx={size / 2}
                        cy={size / 2}
                        r={radius}
                        fill="none"
                        className={colorMap[color]}
                        strokeWidth={strokeWidth}
                        strokeDasharray={circumference}
                        strokeDashoffset={offset}
                        strokeLinecap="round"
                        style={{ transition: "stroke-dashoffset 1s ease-in-out" }}
                    />
                </svg>
                <div className="absolute inset-0 flex items-center justify-center">
                    <span className="text-2xl font-bold text-foreground">{value}%</span>
                </div>
            </div>
            {label && <span className="text-sm font-medium text-foreground">{label}</span>}
            {sublabel && <span className="text-xs text-muted-foreground">{sublabel}</span>}
        </div>
    );
};

export default CircularProgress;
