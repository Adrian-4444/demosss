"use client";

import React, { useState } from "react";
import { useRouter } from "next/navigation";
import { useKeystrokeCapture } from "@/hooks/useKeystrokeCapture";
import { Shield, Key, Mail, Lock, CheckCircle, AlertOctagon, Terminal, HelpCircle, ShieldCheck } from "lucide-react";

export default function LoginPage() {
  const router = useRouter();
  const {
    backspaceCount,
    handleKeyDown,
    handleKeyUp,
    resetKeystrokes,
    getKeystrokeFeatures
  } = useKeystrokeCapture();

  const [email, setEmail] = useState("");
  const [password, setPassword] = useState("");
  
  // Adaptive OTP state
  const [mfaRequired, setMfaRequired] = useState(false);
  const [tempToken, setTempToken] = useState("");
  const [otpCode, setOtpCode] = useState("");
  const [debugOtp, setDebugOtp] = useState("");

  // Lockout / Rejection States
  const [riskDetails, setRiskDetails] = useState<{
    risk_score: number;
    anomalies: string[];
  } | null>(null);

  const [error, setError] = useState("");
  const [loading, setLoading] = useState(false);
  const [success, setSuccess] = useState(false);

  const handleLoginSubmit = async (e: React.FormEvent) => {
    e.preventDefault();
    setError("");
    setRiskDetails(null);
    setLoading(true);

    const features = getKeystrokeFeatures();
    
    // Fallback timings if capture fails
    const dummyFeatures = {
      hold_times: Array(password.length).fill(100.0),
      flight_times: Array(password.length - 1).fill(150.0),
      latencies: Array(password.length - 1).fill(250.0),
      typing_speed: 5.0,
      backspace_count: backspaceCount,
      error_rate: 0.0
    };

    const finalFeatures = features || dummyFeatures;

    try {
      const response = await fetch("http://localhost:8080/api/auth/login", {
        method: "POST",
        headers: { "Content-Type": "application/json" },
        body: JSON.stringify({
          email,
          password,
          keystroke_data: finalFeatures,
          simulation_type: "None"
        })
      });

      const data = await response.json();

      if (!response.ok) {
        // Biometrics high-risk rejection or account lockout
        if (response.status === 403) {
          setRiskDetails({
            risk_score: data.detail.risk_score,
            anomalies: data.detail.anomalies
          });
          throw new Error(data.detail.message || "Behavioral biometrics mismatch. Access Denied.");
        }
        throw new Error(data.detail || "Authentication failed.");
      }

      // Step-up verification (Medium Risk)
      if (data.status === "MFA_REQUIRED") {
        setMfaRequired(true);
        setTempToken(data.temp_token);
        setDebugOtp(data.otp_debug || "");
        return;
      }

      // Successful login
      completeAuthentication(data);

    } catch (err: any) {
      setError(err.message || "Authentication error occurred.");
      resetKeystrokes();
    } finally {
      setLoading(false);
    }
  };

  const handleOtpSubmit = async (e: React.FormEvent) => {
    e.preventDefault();
    setError("");
    setLoading(true);

    try {
      const response = await fetch("http://localhost:8080/api/auth/verify-otp", {
        method: "POST",
        headers: {
          "Content-Type": "application/json",
          "Authorization": `Bearer ${tempToken}`
        },
        body: JSON.stringify({
          email,
          otp: otpCode
        })
      });

      const data = await response.json();

      if (!response.ok) {
        throw new Error(data.detail || "Invalid or expired OTP");
      }

      setMfaRequired(false);
      completeAuthentication(data);

    } catch (err: any) {
      setError(err.message || "OTP verification failed.");
    } finally {
      setLoading(false);
    }
  };

  const completeAuthentication = (data: any) => {
    setSuccess(true);
    localStorage.setItem("token", data.access_token);
    localStorage.setItem("role", data.role);
    localStorage.setItem("username", data.user.name);
    localStorage.setItem("email", data.user.email);
    
    window.dispatchEvent(new Event("storage"));
    
    setTimeout(() => {
      if (data.role === "admin") {
        router.push("/dashboard/admin");
      } else {
        router.push("/dashboard/user");
      }
    }, 1500);
  };

  return (
    <div className="max-w-md w-full mx-auto my-12 px-4 sm:px-0 flex-grow flex flex-col justify-center">
      <div className="glass-panel p-8 rounded-2xl relative overflow-hidden">
        <div className="scanner-line" />

        <div className="text-center mb-8">
          <div className="w-12 h-12 rounded-full bg-indigo-950/50 border border-indigo-700/50 flex items-center justify-center mx-auto text-indigo-400 mb-4 pulse-teal">
            <Lock className="w-6 h-6 text-cyan-400" />
          </div>
          <h2 className="text-2xl font-bold text-slate-100">Secure Corporate Login</h2>
          <p className="text-xs text-slate-450 mt-1">Aegis Dynamics biometrics protected gateway</p>
        </div>

        {error && (
          <div className="p-3 mb-6 bg-rose-950/30 border border-rose-900/50 rounded-lg text-rose-450 text-xs flex gap-2">
            <AlertOctagon className="w-4 h-4 text-rose-400 flex-shrink-0" />
            <div className="flex-grow">
              <span className="font-bold block mb-0.5">AUTHENTICATION FAILED</span>
              <span className="text-[11px] leading-relaxed block">{error}</span>
              
              {riskDetails && (
                <div className="mt-2.5 pt-2.5 border-t border-rose-900/40">
                  <div className="text-[10px] uppercase font-bold text-slate-400 mb-1">Risk Profile Summary:</div>
                  <span className="text-[10px] text-rose-350 block">Risk Score: <strong className="text-rose-400">{riskDetails.risk_score}%</strong> (High Risk Indicator)</span>
                  <div className="mt-1 space-y-0.5">
                    {riskDetails.anomalies.map((anom, idx) => (
                      <span key={idx} className="text-[9.5px] text-slate-300 block">• {anom}</span>
                    ))}
                  </div>
                </div>
              )}
            </div>
          </div>
        )}

        {success ? (
          <div className="text-center py-8">
            <div className="w-16 h-16 bg-emerald-950/50 border border-emerald-500/40 rounded-full flex items-center justify-center mx-auto text-emerald-400 mb-4 animate-bounce">
              <ShieldCheck className="w-8 h-8" />
            </div>
            <h3 className="text-lg font-bold text-slate-200">Signature Matches</h3>
            <p className="text-xs text-slate-405 mt-2">Biometrics verification verified. Access granted...</p>
          </div>
        ) : mfaRequired ? (
          /* STEP-UP MFA CHALLENGE INTERFACE */
          <div className="space-y-4">
            <div className="p-3 mb-4 bg-yellow-950/20 border border-yellow-900/40 rounded-lg text-slate-350 text-xs">
              <span className="font-bold text-yellow-400 block mb-1">Adaptive Security Triggered</span>
              Your password matched, but typing biometrics indicates a slight cadence deviation. A secondary validation code was triggered.
            </div>

            {/* Developer debug helper */}
            {debugOtp && (
              <div className="p-2 mb-4 bg-slate-900 border border-slate-800 rounded font-mono text-[10px] text-cyan-400 flex justify-between items-center">
                <span>[DEMO SIMULATOR] MFA OTP: <strong>{debugOtp}</strong></span>
                <span className="text-[9px] text-slate-500">Auto-sent</span>
              </div>
            )}

            <form onSubmit={handleOtpSubmit} className="space-y-4">
              <div>
                <label className="block text-xs font-semibold text-slate-350 mb-1.5 uppercase tracking-wide">6-Digit Verification Code</label>
                <input
                  type="text"
                  required
                  maxLength={6}
                  value={otpCode}
                  onChange={(e) => setOtpCode(e.target.value)}
                  placeholder="123456"
                  className="w-full bg-slate-900/60 border border-slate-800 rounded-lg px-4 py-2.5 text-center text-lg font-mono tracking-widest text-slate-200 focus:outline-none focus:border-cyan-500 transition-colors"
                />
              </div>

              <button
                type="submit"
                disabled={loading || otpCode.length < 6}
                className="w-full btn-cyber-primary text-white text-sm font-semibold py-3 rounded-lg flex items-center justify-center gap-1.5 cursor-pointer disabled:opacity-50"
              >
                Verify Code & Authenticate
              </button>
            </form>
          </div>
        ) : (
          /* STANDARD LOGIN INTERFACE */
          <form onSubmit={handleLoginSubmit} className="space-y-4">
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
              <label className="block text-xs font-semibold text-slate-350 mb-1.5 uppercase tracking-wide">Password</label>
              <div className="relative">
                <Key className="absolute left-3 top-3 w-4 h-4 text-slate-500" />
                <input
                  type="password"
                  required
                  value={password}
                  onChange={(e) => setPassword(e.target.value)}
                  onKeyDown={handleKeyDown}
                  onKeyUp={handleKeyUp}
                  autoComplete="off"
                  placeholder="••••••••••••"
                  className="w-full bg-slate-900/60 border border-slate-800 rounded-lg pl-10 pr-4 py-2.5 text-slate-200 text-sm focus:outline-none focus:border-indigo-500 transition-colors tracking-widest"
                />
              </div>
            </div>

            <button
              type="submit"
              disabled={loading || password.length === 0}
              className="w-full btn-cyber-primary text-white text-sm font-semibold py-3 rounded-lg flex items-center justify-center gap-1.5 mt-6 cursor-pointer disabled:opacity-50"
            >
              Sign In Securely
            </button>
          </form>
        )}
      </div>
    </div>
  );
}
