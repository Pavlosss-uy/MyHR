import { useState } from "react";
import { motion } from "framer-motion";
import Navbar from "@/components/Navbar";
import { Button } from "@/components/ui/button";
import { Input } from "@/components/ui/input";
import { Label } from "@/components/ui/label";
import { Switch } from "@/components/ui/switch";
import { Slider } from "@/components/ui/slider";
import { User, Bell, Mic, CreditCard, Shield, ChevronRight, CheckCircle2 } from "lucide-react";
import { cn } from "@/lib/utils";
import { useToast } from "@/hooks/use-toast";

const tabs = [
    { id: "profile", label: "Profile", icon: User },
    { id: "voice", label: "Voice & Audio", icon: Mic },
    { id: "notifications", label: "Notifications", icon: Bell },
    { id: "subscription", label: "Subscription", icon: CreditCard },
    { id: "security", label: "Security", icon: Shield },
];

const plans = [
    { name: "Free", price: "$0", period: "/month", features: ["3 mock interviews/month", "Basic feedback", "Email support"], current: false },
    { name: "Pro", price: "$29", period: "/month", features: ["Unlimited interviews", "Detailed AI feedback", "Priority support", "Custom JD uploads"], current: true },
    { name: "Enterprise", price: "$99", period: "/month", features: ["Everything in Pro", "Team management", "API access", "Custom integrations", "Dedicated account manager"], current: false },
];

const Settings = () => {
    const [activeTab, setActiveTab] = useState("profile");
    const [sensitivity, setSensitivity] = useState([70]);
    const { toast } = useToast();

    const handleSaveProfile = () => {
        toast({
            title: "Profile updated",
            description: "Your profile changes have been saved successfully.",
        });
    };

    const handleUpdatePassword = () => {
        toast({
            title: "Password updated",
            description: "Your password has been changed successfully.",
        });
    };

    return (
        <div className="min-h-screen bg-background">
            <Navbar />
            <main className="pt-24 pb-12 max-w-6xl mx-auto px-6">
                <motion.div
                    initial={{ opacity: 0, y: 10 }}
                    animate={{ opacity: 1, y: 0 }}
                    className="mb-8"
                >
                    <h1 className="text-2xl font-bold text-foreground">Settings</h1>
                    <p className="text-muted-foreground mt-1">Manage your account, preferences, and subscription.</p>
                </motion.div>

                <div className="flex flex-col md:flex-row gap-6">
                    {/* Sidebar */}
                    <nav className="md:w-60 shrink-0">
                        <div className="bg-card rounded-xl border border-border shadow-sm p-2 space-y-0.5">
                            {tabs.map((tab) => (
                                <button
                                    key={tab.id}
                                    onClick={() => setActiveTab(tab.id)}
                                    className={cn(
                                        "w-full flex items-center gap-3 px-3 py-2.5 rounded-lg text-sm font-medium transition-colors text-left",
                                        activeTab === tab.id
                                            ? "bg-primary/5 text-primary"
                                            : "text-muted-foreground hover:text-foreground hover:bg-muted"
                                    )}
                                >
                                    <tab.icon className="w-4 h-4" />
                                    {tab.label}
                                    {activeTab === tab.id && <ChevronRight className="w-3.5 h-3.5 ml-auto" />}
                                </button>
                            ))}
                        </div>
                    </nav>

                    {/* Content */}
                    <div className="flex-1">
                        {activeTab === "profile" && (
                            <motion.div
                                initial={{ opacity: 0, x: 10 }}
                                animate={{ opacity: 1, x: 0 }}
                                className="bg-card rounded-xl border border-border shadow-sm"
                            >
                                <div className="p-5 border-b border-border">
                                    <h2 className="font-semibold text-foreground">Profile Information</h2>
                                    <p className="text-sm text-muted-foreground mt-0.5">Update your personal details and photo.</p>
                                </div>
                                <div className="p-5 space-y-5">
                                    <div className="flex items-center gap-4">
                                        <div className="w-16 h-16 rounded-full gradient-cobalt flex items-center justify-center text-xl font-bold text-primary-foreground">
                                            AD
                                        </div>
                                        <div>
                                            <Button variant="outline" size="sm">Change Photo</Button>
                                            <p className="text-xs text-muted-foreground mt-1">JPG, PNG. Max 5MB.</p>
                                        </div>
                                    </div>
                                    <div className="grid sm:grid-cols-2 gap-4">
                                        <div className="space-y-2">
                                            <Label>First Name</Label>
                                            <Input defaultValue="Alex" />
                                        </div>
                                        <div className="space-y-2">
                                            <Label>Last Name</Label>
                                            <Input defaultValue="Developer" />
                                        </div>
                                        <div className="space-y-2">
                                            <Label>Email</Label>
                                            <Input type="email" defaultValue="alex@company.com" />
                                        </div>
                                        <div className="space-y-2">
                                            <Label>Role</Label>
                                            <Input defaultValue="Senior Engineer" />
                                        </div>
                                    </div>
                                    <div className="pt-2">
                                        <Button variant="hero" onClick={handleSaveProfile}>Save Changes</Button>
                                    </div>
                                </div>
                            </motion.div>
                        )}

                        {activeTab === "voice" && (
                            <motion.div
                                initial={{ opacity: 0, x: 10 }}
                                animate={{ opacity: 1, x: 0 }}
                                className="bg-card rounded-xl border border-border shadow-sm"
                            >
                                <div className="p-5 border-b border-border">
                                    <h2 className="font-semibold text-foreground">Voice & Audio Settings</h2>
                                    <p className="text-sm text-muted-foreground mt-0.5">Configure microphone sensitivity and audio preferences.</p>
                                </div>
                                <div className="p-5 space-y-6">
                                    <div className="space-y-3">
                                        <div className="flex items-center justify-between">
                                            <Label>Microphone Sensitivity</Label>
                                            <span className="text-sm font-medium text-foreground">{sensitivity[0]}%</span>
                                        </div>
                                        <Slider value={sensitivity} onValueChange={setSensitivity} max={100} step={1} className="w-full" />
                                    </div>
                                    <div className="flex items-center justify-between py-3 border-b border-border">
                                        <div>
                                            <p className="text-sm font-medium text-foreground">Noise Cancellation</p>
                                            <p className="text-xs text-muted-foreground">Filter background noise during interviews</p>
                                        </div>
                                        <Switch defaultChecked />
                                    </div>
                                    <div className="flex items-center justify-between py-3 border-b border-border">
                                        <div>
                                            <p className="text-sm font-medium text-foreground">Auto-Pause Detection</p>
                                            <p className="text-xs text-muted-foreground">Detect when you pause speaking</p>
                                        </div>
                                        <Switch defaultChecked />
                                    </div>
                                    <div className="flex items-center justify-between py-3">
                                        <div>
                                            <p className="text-sm font-medium text-foreground">Record Interviews</p>
                                            <p className="text-xs text-muted-foreground">Save recordings for later review</p>
                                        </div>
                                        <Switch />
                                    </div>
                                </div>
                            </motion.div>
                        )}

                        {activeTab === "notifications" && (
                            <motion.div
                                initial={{ opacity: 0, x: 10 }}
                                animate={{ opacity: 1, x: 0 }}
                                className="bg-card rounded-xl border border-border shadow-sm"
                            >
                                <div className="p-5 border-b border-border">
                                    <h2 className="font-semibold text-foreground">Notification Preferences</h2>
                                </div>
                                <div className="p-5 space-y-1">
                                    {["Interview reminders", "Feedback reports ready", "Weekly progress digest", "Tips & suggestions", "Product updates"].map((item) => (
                                        <div key={item} className="flex items-center justify-between py-3 border-b border-border last:border-0">
                                            <span className="text-sm text-foreground">{item}</span>
                                            <Switch defaultChecked={item !== "Product updates"} />
                                        </div>
                                    ))}
                                </div>
                            </motion.div>
                        )}

                        {activeTab === "subscription" && (
                            <motion.div
                                initial={{ opacity: 0, x: 10 }}
                                animate={{ opacity: 1, x: 0 }}
                                className="space-y-6"
                            >
                                <div className="grid sm:grid-cols-3 gap-4">
                                    {plans.map((plan) => (
                                        <div
                                            key={plan.name}
                                            className={cn(
                                                "bg-card rounded-xl border-2 p-6 transition-all",
                                                plan.current
                                                    ? "border-cobalt shadow-cobalt"
                                                    : "border-border hover:border-cobalt-lighter"
                                            )}
                                        >
                                            {plan.current && (
                                                <span className="inline-block text-xs font-semibold text-cobalt bg-cobalt/10 px-2 py-0.5 rounded-full mb-3">
                                                    Current Plan
                                                </span>
                                            )}
                                            <h3 className="text-lg font-bold text-foreground">{plan.name}</h3>
                                            <div className="mt-2 mb-4">
                                                <span className="text-3xl font-extrabold text-foreground">{plan.price}</span>
                                                <span className="text-sm text-muted-foreground">{plan.period}</span>
                                            </div>
                                            <ul className="space-y-2 mb-6">
                                                {plan.features.map((f) => (
                                                    <li key={f} className="flex items-center gap-2 text-sm text-muted-foreground">
                                                        <CheckCircle2 className="w-3.5 h-3.5 text-mint shrink-0" />
                                                        {f}
                                                    </li>
                                                ))}
                                            </ul>
                                            <Button
                                                variant={plan.current ? "outline" : "hero"}
                                                size="sm"
                                                className="w-full"
                                                disabled={plan.current}
                                            >
                                                {plan.current ? "Current" : "Upgrade"}
                                            </Button>
                                        </div>
                                    ))}
                                </div>
                            </motion.div>
                        )}

                        {activeTab === "security" && (
                            <motion.div
                                initial={{ opacity: 0, x: 10 }}
                                animate={{ opacity: 1, x: 0 }}
                                className="bg-card rounded-xl border border-border shadow-sm"
                            >
                                <div className="p-5 border-b border-border">
                                    <h2 className="font-semibold text-foreground">Security</h2>
                                </div>
                                <div className="p-5 space-y-5">
                                    <div className="space-y-2">
                                        <Label>Current Password</Label>
                                        <Input type="password" placeholder="••••••••" />
                                    </div>
                                    <div className="space-y-2">
                                        <Label>New Password</Label>
                                        <Input type="password" placeholder="••••••••" />
                                    </div>
                                    <div className="flex items-center justify-between py-3 border-t border-border">
                                        <div>
                                            <p className="text-sm font-medium text-foreground">Two-Factor Authentication</p>
                                            <p className="text-xs text-muted-foreground">Add extra security to your account</p>
                                        </div>
                                        <Switch />
                                    </div>
                                    <Button variant="hero" onClick={handleUpdatePassword}>Update Password</Button>
                                </div>
                            </motion.div>
                        )}
                    </div>
                </div>
            </main>
        </div>
    );
};

export default Settings;
