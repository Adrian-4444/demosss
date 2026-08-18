import Link from "next/link";
import { Shield, Key, Cpu, AlertTriangle, CheckCircle, Terminal, HelpCircle, ArrowRight, Activity, Database, Lock } from "lucide-react";

export default function LandingPage() {
  return (
    <div className="max-w-7xl mx-auto px-4 sm:px-6 lg:px-8 py-12 flex-grow flex flex-col justify-center">
      {/* Hero Banner Section */}
      <div className="text-center max-w-3xl mx-auto mb-16">
        <div className="inline-flex items-center gap-1.5 px-3 py-1 rounded-full bg-indigo-900/30 border border-indigo-700/50 text-indigo-400 text-xs font-semibold uppercase tracking-wider mb-6 animate-pulse">
          <Activity className="w-3.5 h-3.5" />
          Behavioral Biometrics Core v1.2
        </div>
        <h1 className="text-4xl sm:text-5xl font-extrabold tracking-tight text-white mb-6">
          AI Powered Keystroke Dynamics <span className="text-transparent bg-clip-text bg-gradient-to-r from-cyan-400 to-indigo-400">Authentication System</span>
        </h1>
        <p className="text-base sm:text-lg text-slate-400 leading-relaxed mb-8">
          Traditional passwords are easily stolen. Our system secures authentication by introducing a second, invisible layer of protection: analyzing <strong>how</strong> you type your password. If an attacker steals your credentials, our AI blocks them instantly based on rhythm anomalies.
        </p>
        <div className="flex flex-wrap justify-center gap-4">
          <Link href="/register" className="btn-cyber-primary px-6 py-3 rounded-lg text-sm font-semibold text-white tracking-wide flex items-center gap-2">
            Enroll Typing Profile
            <ArrowRight className="w-4 h-4" />
          </Link>
          <Link href="/login" className="btn-cyber-secondary px-6 py-3 rounded-lg text-sm font-semibold text-slate-200 tracking-wide flex items-center gap-2">
            Try Secure Login
          </Link>
          <Link href="/simulations" className="px-6 py-3 rounded-lg text-sm font-semibold text-cyan-400 bg-cyan-950/20 border border-cyan-800/40 hover:bg-cyan-900/30 transition-colors flex items-center gap-2">
            <Terminal className="w-4 h-4" />
            Attack Simulator
          </Link>
        </div>
      </div>

      {/* The Core Concept Breakdown */}
      <div className="grid grid-cols-1 lg:grid-cols-2 gap-8 mb-16">
        <div className="glass-panel p-8 rounded-2xl relative overflow-hidden flex flex-col justify-between">
          <div className="scanner-line" />
          <div>
            <div className="w-12 h-12 rounded-xl bg-cyan-950/50 border border-cyan-800/40 flex items-center justify-center text-cyan-400 mb-6">
              <Cpu className="w-6 h-6" />
            </div>
            <h2 className="text-2xl font-bold text-slate-100 mb-4">How Keystroke Timing Works</h2>
            <p className="text-slate-400 text-sm leading-relaxed mb-6">
              When typing, humans exhibit unique behavioral timings:
            </p>
            <div className="space-y-4">
              <div className="flex gap-3">
                <span className="flex-shrink-0 w-6 h-6 rounded-md bg-indigo-950 border border-indigo-700/50 flex items-center justify-center text-xs font-semibold text-indigo-400">1</span>
                <div>
                  <h4 className="text-sm font-semibold text-slate-200">Key Hold Time (HT)</h4>
                  <p className="text-xs text-slate-450">The duration in milliseconds a key is held down. Determined by finger pressure and key release speed.</p>
                </div>
              </div>
              <div className="flex gap-3">
                <span className="flex-shrink-0 w-6 h-6 rounded-md bg-indigo-950 border border-indigo-700/50 flex items-center justify-center text-xs font-semibold text-indigo-400">2</span>
                <div>
                  <h4 className="text-sm font-semibold text-slate-200">Flight Time (FT)</h4>
                  <p className="text-xs text-slate-450">The duration in milliseconds between releasing a key and pressing the next key in sequence.</p>
                </div>
              </div>
              <div className="flex gap-3">
                <span className="flex-shrink-0 w-6 h-6 rounded-md bg-indigo-950 border border-indigo-700/50 flex items-center justify-center text-xs font-semibold text-indigo-400">3</span>
                <div>
                  <h4 className="text-sm font-semibold text-slate-200">Digraph & Trigraph Latency</h4>
                  <p className="text-xs text-slate-450">Timing combinations of two (digraphs) or three (trigraphs) sequential characters, characterizing muscle memory habits.</p>
                </div>
              </div>
            </div>
          </div>
          <div className="mt-8 pt-6 border-t border-slate-800/60 flex items-center justify-between text-xs text-slate-500">
            <span>Accuracy Rate: up to 98.7%</span>
            <span>Feature Vector size: 3L - 2</span>
          </div>
        </div>

        <div className="glass-panel p-8 rounded-2xl flex flex-col justify-between border-cyan-800/20">
          <div>
            <div className="w-12 h-12 rounded-xl bg-indigo-950/50 border border-indigo-800/40 flex items-center justify-center text-indigo-400 mb-6">
              <Shield className="w-6 h-6" />
            </div>
            <h2 className="text-2xl font-bold text-slate-100 mb-4">Zero Trust & Continuous Authentication</h2>
            <p className="text-slate-400 text-sm leading-relaxed mb-6">
              By continuously checking keystroke patterns, Aegis Dynamics introduces adaptive login policies that verify identities without interrupting the user.
            </p>
            <div className="grid grid-cols-1 sm:grid-cols-2 gap-4">
              <div className="p-4 rounded-xl bg-slate-900/60 border border-slate-800/40">
                <div className="flex items-center gap-2 mb-2">
                  <CheckCircle className="w-4 h-4 text-emerald-400" />
                  <span className="text-xs font-bold text-slate-200">Credential Protection</span>
                </div>
                <p className="text-[11px] text-slate-400">Blocks login attempts made using correct, stolen password strings typed with suspicious/robotic dynamics.</p>
              </div>
              
              <div className="p-4 rounded-xl bg-slate-900/60 border border-slate-800/40">
                <div className="flex items-center gap-2 mb-2">
                  <CheckCircle className="w-4 h-4 text-emerald-400" />
                  <span className="text-xs font-bold text-slate-200">Adaptive Authentication</span>
                </div>
                <p className="text-[11px] text-slate-400">Prompts for an OTP challenge only if the user types with minor variation, balancing user experience and safety.</p>
              </div>

              <div className="p-4 rounded-xl bg-slate-900/60 border border-slate-800/40">
                <div className="flex items-center gap-2 mb-2">
                  <AlertTriangle className="w-4 h-4 text-rose-400" />
                  <span className="text-xs font-bold text-slate-200">Bot Signature Defenses</span>
                </div>
                <p className="text-[11px] text-slate-400">Instantly locks out automated script logins by checking for perfect uniform key intervals (std dev = 0).</p>
              </div>

              <div className="p-4 rounded-xl bg-slate-900/60 border border-slate-800/40">
                <div className="flex items-center gap-2 mb-2">
                  <AlertTriangle className="w-4 h-4 text-rose-400" />
                  <span className="text-xs font-bold text-slate-200">Credential Stuffing</span>
                </div>
                <p className="text-[11px] text-slate-400">Catches clipboard-paste automated injections, where flight times between characters are logged as exactly zero.</p>
              </div>
            </div>
          </div>
          <div className="mt-8 pt-6 border-t border-slate-800/60 flex items-center justify-between text-xs text-slate-500">
            <span>Adaptive MFA Fallback: Yes</span>
            <span>Credential Hashing: bcrypt (rounds 12)</span>
          </div>
        </div>
      </div>

      {/* Cyber Security Concepts Section */}
      <h3 className="text-xl font-bold text-slate-100 mb-6 text-center">Cybersecurity Controls Implemented</h3>
      <div className="grid grid-cols-2 md:grid-cols-4 gap-4 mb-12 text-center">
        <div className="p-4 rounded-xl bg-slate-900/40 border border-slate-800/30 flex flex-col items-center">
          <Lock className="w-5 h-5 text-indigo-400 mb-2" />
          <span className="text-xs font-semibold text-slate-300">OWASP Top 10</span>
        </div>
        <div className="p-4 rounded-xl bg-slate-900/40 border border-slate-800/30 flex flex-col items-center">
          <Database className="w-5 h-5 text-indigo-400 mb-2" />
          <span className="text-xs font-semibold text-slate-300">Prepared SQL</span>
        </div>
        <div className="p-4 rounded-xl bg-slate-900/40 border border-slate-800/30 flex flex-col items-center">
          <Key className="w-5 h-5 text-indigo-400 mb-2" />
          <span className="text-xs font-semibold text-slate-300">Brute Force Lockouts</span>
        </div>
        <div className="p-4 rounded-xl bg-slate-900/40 border border-slate-800/30 flex flex-col items-center">
          <Activity className="w-5 h-5 text-indigo-400 mb-2" />
          <span className="text-xs font-semibold text-slate-300">Audit Trail Logs</span>
        </div>
      </div>
    </div>
  );
}
