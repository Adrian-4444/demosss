"use client";

import React, { useState } from "react";
import { useRouter } from "next/navigation";
import { useKeystrokeCapture, KeystrokeFeatures } from "@/hooks/useKeystrokeCapture";
import { Shield, Key, User, Mail, CheckCircle, Info, Keyboard, Activity, RefreshCw, ChevronRight } from "lucide-react";

export default function RegisterPage() {
  const router = useRouter();
  const {
    backspaceCount,
    handleKeyDown,
    handleKeyUp,
    resetKeystrokes,
    getKeystrokeFeatures
  } = useKeystrokeCapture();

  // Step 1: Account info
  const [step, setStep] = useState(1);
  const [name, setName] = useState("");
  const [email, setEmail] = useState("");
  const [password, setPassword] = useState("");
  const [confirmPassword, setConfirmPassword] = useState("");
  
  // Step 2: Biometrics
  const [trialCount, setTrialCount] = useState(0);
  const [trialPassword, setTrialPassword] = useState("");
  const [collectedSamples, setCollectedSamples] = useState<KeystrokeFeatures[]>([]);
  const [currentSampleSpeed, setCurrentSampleSpeed] = useState<number | null>(null);
  
  const [error, setError] = useState("");
  const [loading, setLoading] = useState(false);
  const [success, setSuccess] = useState(false);

  const handleProceedToEnrollment = (e: React.FormEvent) => {
    e.preventDefault();
    setError("");
    
    if (!name || !email || !password) {
      setError("Please fill out all credentials.");
      return;
    }
    
    if (password.length < 6) {
      setError("Password must be at least 6 characters long.");
      return;
    }
    
    if (password !== confirmPassword) {
      setError("Passwords do not match.");
      return;
    }
    
    setStep(2);
  };

  const handleTrialSubmit = (e: React.FormEvent) => {
    e.preventDefault();
    setError("");

    if (trialPassword !== password) {
      setError("Entered password does not match the password specified in Step 1.");
      setTrialPassword("");
      resetKeystrokes();
      return;
    }

    const features = getKeystrokeFeatures();
    if (!features) {
      setError("Please type the password continuously and normally.");
      setTrialPassword("");
      resetKeystrokes();
      return;
    }

    if (features.backspace_count > 0) {
      setError("Sample discarded. To establish a clean baseline profile, please type your password without pressing Backspace.");
      setTrialPassword("");
      resetKeystrokes();
      return;
    }

    // Save sample
    setCollectedSamples(prev => [...prev, features]);
    setCurrentSampleSpeed(features.typing_speed);
    
    const nextTrial = trialCount + 1;
    setTrialCount(nextTrial);
    setTrialPassword("");
    resetKeystrokes();

    if (nextTrial >= 10) {
      // Auto-submit registration once 10 samples are logged
      submitRegistration([...collectedSamples, features]);
    }
  };

  const submitRegistration = async (finalSamples: KeystrokeFeatures[]) => {
    setLoading(true);
    setError("");
    
    try {
      const response = await fetch("http://localhost:8080/api/auth/register", {
        method: "POST",
        headers: { "Content-Type": "application/json" },
        body: JSON.stringify({
          name,
          email,
          password,
          keystroke_samples: finalSamples
        })
      });

      const data = await response.json();
      
      if (!response.ok) {
        throw new Error(data.detail || "Registration failed");
      }

      setSuccess(true);
      
      // Store credentials in localStorage
      localStorage.setItem("token", data.access_token);
      localStorage.setItem("role", data.role);
      localStorage.setItem("username", data.user.name);
      localStorage.setItem("email", data.user.email);
      
      // Trigger a window event to update Navbar layout state
      window.dispatchEvent(new Event("storage"));
      
      setTimeout(() => {
        router.push("/dashboard/user");
      }, 2000);
      
    } catch (err: any) {
      setError(err.message || "An error occurred during registration.");
      // Rollback step if registration request fails
      setTrialCount(0);
      setCollectedSamples([]);
      setStep(1);
    } finally {
      setLoading(false);
    }
  };

  const resetEnrollment = () => {
    setTrialCount(0);
    setCollectedSamples([]);
    setTrialPassword("");
    setError("");
    resetKeystrokes();
  };

  return (
    <div className="max-w-md w-full mx-auto my-12 px-4 sm:px-0 flex-grow flex flex-col justify-center">
      <div className="glass-panel p-8 rounded-2xl relative overflow-hidden">
        <div className="scanner-line" />
        
        <div className="text-center mb-8">
          <div className="w-12 h-12 rounded-full bg-indigo-950/50 border border-indigo-700/50 flex items-center justify-center mx-auto text-indigo-400 mb-4 pulse-teal">
            <Shield className="w-6 h-6 text-cyan-400" />
          </div>
          <h2 className="text-2xl font-bold text-slate-100">Enroll Security Profile</h2>
          <p className="text-xs text-slate-400 mt-1">Register password and map behavioral keystroke biometrics</p>
        </div>

        {error && (
          <div className="p-3 mb-6 bg-rose-950/30 border border-rose-900/50 rounded-lg text-rose-400 text-xs flex gap-2">
            <span className="font-bold flex-shrink-0">ALERT:</span>
            <span>{error}</span>
          </div>
        )}

        {success ? (
          <div className="text-center py-8">
            <div className="w-16 h-16 bg-emerald-950/50 border border-emerald-500/40 rounded-full flex items-center justify-center mx-auto text-emerald-400 mb-4 animate-bounce">
              <CheckCircle className="w-8 h-8" />
            </div>
            <h3 className="text-lg font-bold text-slate-200">Enrolled Successfully</h3>
            <p className="text-xs text-slate-400 mt-2">AI typing model trained. Directing to your dashboard...</p>
          </div>
        ) : (
          <div>
            {step === 1 ? (
              /* STEP 1: CREDENTIALS */
              <form onSubmit={handleProceedToEnrollment} className="space-y-4">
                <div>
                  <label className="block text-xs font-semibold text-slate-350 mb-1.5 uppercase tracking-wide">Full Name</label>
                  <div className="relative">
                    <User className="absolute left-3 top-3 w-4 h-4 text-slate-500" />
                    <input
                      type="text"
                      required
                      value={name}
                      onChange={(e) => setName(e.target.value)}
                      placeholder="e.g. John Doe"
                      className="w-full bg-slate-900/60 border border-slate-800 rounded-lg pl-10 pr-4 py-2.5 text-slate-200 text-sm focus:outline-none focus:border-indigo-500 transition-colors"
                    />
                  </div>
                </div>

                <div>
                  <label className="block text-xs font-semibold text-slate-350 mb-1.5 uppercase tracking-wide">Corporate Email</label>
                  <div className="relative">
                    <Mail className="absolute left-3 top-3 w-4 h-4 text-slate-500" />
                    <input
                      type="email"
                      required
                      value={email}
                      onChange={(e) => setEmail(e.target.value)}
                      placeholder="john@banking.com"
                      className="w-full bg-slate-900/60 border border-slate-800 rounded-lg pl-10 pr-4 py-2.5 text-slate-200 text-sm focus:outline-none focus:border-indigo-500 transition-colors"
                    />
                  </div>
                </div>

                <div>
                  <label className="block text-xs font-semibold text-slate-350 mb-1.5 uppercase tracking-wide">Password (Secret Key)</label>
                  <div className="relative">
                    <Key className="absolute left-3 top-3 w-4 h-4 text-slate-500" />
                    <input
                      type="password"
                      required
                      value={password}
                      onChange={(e) => setPassword(e.target.value)}
                      placeholder="••••••••••••"
                      className="w-full bg-slate-900/60 border border-slate-800 rounded-lg pl-10 pr-4 py-2.5 text-slate-200 text-sm focus:outline-none focus:border-indigo-500 transition-colors"
                    />
                  </div>
                </div>

                <div>
                  <label className="block text-xs font-semibold text-slate-350 mb-1.5 uppercase tracking-wide">Confirm Password</label>
                  <div className="relative">
                    <Key className="absolute left-3 top-3 w-4 h-4 text-slate-500" />
                    <input
                      type="password"
                      required
                      value={confirmPassword}
                      onChange={(e) => setConfirmPassword(e.target.value)}
                      placeholder="••••••••••••"
                      className="w-full bg-slate-900/60 border border-slate-800 rounded-lg pl-10 pr-4 py-2.5 text-slate-200 text-sm focus:outline-none focus:border-indigo-500 transition-colors"
                    />
                  </div>
                </div>

                <button
                  type="submit"
                  className="w-full btn-cyber-primary text-white text-sm font-semibold py-3 rounded-lg flex items-center justify-center gap-1.5 mt-6 cursor-pointer"
                >
                  Proceed to Biometrics
                  <ChevronRight className="w-4 h-4" />
                </button>
              </form>
            ) : (
              /* STEP 2: BIOMETRICS ENROLLMENT */
              <div>
                {/* Information Card */}
                <div className="p-3 mb-6 bg-indigo-950/20 border border-indigo-900/40 rounded-lg text-slate-400 text-xs flex gap-2.5">
                  <Info className="w-5 h-5 text-indigo-400 flex-shrink-0" />
                  <div>
                    <span className="font-bold text-slate-300">Biometric Profiling Phase:</span> Please type your password exactly <strong>10 times</strong> at your normal typing speed to train the AI model. 
                    <span className="block mt-1 text-[11px] text-cyan-400">Do not use backspace during typing to ensure a clean profile baseline.</span>
                  </div>
                </div>

                {/* Progress Indicators */}
                <div className="mb-6">
                  <div className="flex justify-between items-center text-xs mb-2">
                    <span className="font-bold text-slate-300 uppercase tracking-wider flex items-center gap-1">
                      <Keyboard className="w-4 h-4 text-cyan-400" />
                      Captured Profiles
                    </span>
                    <span className="font-bold text-cyan-450">{trialCount} / 10 Complete</span>
                  </div>
                  <div className="flex gap-1.5">
                    {Array.from({ length: 10 }).map((_, idx) => (
                      <div
                        key={idx}
                        className={`flex-grow h-2.5 rounded-full transition-all duration-350 ${
                          idx < trialCount
                            ? "bg-gradient-to-r from-indigo-500 to-cyan-400"
                            : "bg-slate-800/80 border border-slate-700/30"
                        }`}
                      />
                    ))}
                  </div>
                </div>

                {/* Input Trial Form */}
                <form onSubmit={handleTrialSubmit} className="space-y-4">
                  <div>
                    <label className="block text-xs font-semibold text-slate-350 mb-1.5 uppercase tracking-wide">
                      Type Password (Attempt {trialCount + 1})
                    </label>
                    <div className="relative">
                      <Key className="absolute left-3 top-3 w-4 h-4 text-slate-500" />
                      <input
                        type="password"
                        required
                        value={trialPassword}
                        onChange={(e) => setTrialPassword(e.target.value)}
                        onKeyDown={handleKeyDown}
                        onKeyUp={handleKeyUp}
                        autoComplete="off"
                        placeholder="Type password..."
                        className="w-full bg-slate-900/60 border border-slate-800 rounded-lg pl-10 pr-4 py-2.5 text-slate-200 text-sm focus:outline-none focus:border-cyan-500 transition-colors tracking-widest"
                      />
                    </div>
                  </div>

                  <div className="flex items-center justify-between text-xs text-slate-500 mt-2">
                    <span className="flex items-center gap-1.5">
                      <Activity className="w-3.5 h-3.5" />
                      Speed: {currentSampleSpeed ? `${currentSampleSpeed} keys/sec` : "Waiting..."}
                    </span>
                    <button
                      type="button"
                      onClick={resetEnrollment}
                      className="text-rose-450 hover:underline flex items-center gap-1 bg-transparent border-none cursor-pointer"
                    >
                      <RefreshCw className="w-3.5 h-3.5" />
                      Reset Trial
                    </button>
                  </div>

                  <button
                    type="submit"
                    disabled={loading || trialPassword.length === 0}
                    className="w-full btn-cyber-primary text-white text-sm font-semibold py-3 rounded-lg flex items-center justify-center gap-1.5 mt-6 disabled:opacity-50 disabled:cursor-not-allowed cursor-pointer"
                  >
                    {loading ? (
                      <span className="flex items-center gap-1.5">
                        <RefreshCw className="w-4 h-4 animate-spin" />
                        Training AI Model...
                      </span>
                    ) : (
                      "Submit Sample"
                    )}
                  </button>
                </form>
              </div>
            )}
          </div>
        )}
      </div>
    </div>
  );
}
