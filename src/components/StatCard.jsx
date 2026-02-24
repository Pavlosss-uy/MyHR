import { cn } from "@/lib/utils";

const StatCard = ({ icon: Icon, label, value, change, changeType = "neutral", className }) => {
    return (
        <div className={cn("bg-card rounded-xl p-5 border border-border shadow-sm hover:shadow-md transition-shadow", className)}>
            <div className="flex items-start justify-between">
                <div className="w-10 h-10 rounded-lg bg-primary/5 flex items-center justify-center">
                    <Icon className="w-5 h-5 text-primary" />
                </div>
                {change && (
                    <span
                        className={cn(
                            "text-xs font-medium px-2 py-0.5 rounded-full",
                            changeType === "positive" && "bg-mint-light text-mint-dark",
                            changeType === "negative" && "bg-destructive/10 text-destructive",
                            changeType === "neutral" && "bg-muted text-muted-foreground"
                        )}
                    >
                        {change}
                    </span>
                )}
            </div>
            <div className="mt-3">
                <p className="text-2xl font-bold text-foreground">{value}</p>
                <p className="text-sm text-muted-foreground mt-0.5">{label}</p>
            </div>
        </div>
    );
};

export default StatCard;
