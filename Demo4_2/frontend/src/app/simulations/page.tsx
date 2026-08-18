"use client";

import React, { useState, useEffect } from "react";
import { Terminal, ShieldAlert, ShieldCheck, Play, Key, RefreshCw, AlertTriangle, Eye, ShieldCheck as CheckIcon, Clock, Cpu } from "lucide-react";

export default function SimulationsPage() {
  const [targetUser, setTargetUser] = useState("john@banking.com");
  const [attackType, setAttackType] = useState("paste"); // 'paste', 'bot', 'brute', 'impersonate'
  const [consoleLogs, setConsoleLogs] = useState<string[]>([]);
  const [loading, setLoading] = useState(false);
  
  // Results display
  const [result, setResult] = useState<{
    status: boolean;
    statusCode: number;
    riskScore: number;
    riskLevel: string;
    anomalies: string[];
    details: string;
  } | null>(null);

  // Seed passwords mapping for simulation
  const passwords: Dict<string, string> = {
    "admin@banking.com": "AdminPassword123",
    "john@banking.com": "SecureJohn99",
    "jane@banking.com": "JaneP@ssword"
  };

  const addLog = (message: string) => {
    setConsoleLogs(prev => [...prev, `[${new Date().toLocaleTimeString()}] ${message}`]);
  };

  useEffect(() => {
    setConsoleLogs([]);
    addLog(`System initialized. Target user set to: ${targetUser}`);
    addLog(`Ready to execute simulated biometrics attack profiles.`);
  }, [targetUser]);

  const runSimulation = async () => {
    setLoading(true);
    setResult(null);
    setConsoleLogs([]);
    const password = passwords[targetUser];
    
    addLog(`COMMENCING ATTACK SIMULATION: ${attackType.toUpperCase()}`);
    addLog(`Target: ${targetUser} | Password: ${password}`);

    let keystrokeData: any = {};
    let url = "http://localhost:8080/api/auth/login";
    let payload: any = {};

    try {
      if (attackType === "paste") {
        // --- 1. PASTE ATTACK (Credential Stuffing) ---
        addLog("Simulating clipboard paste injection...");
        addLog("Generating timing features: hold times = 1ms, flight times = 0ms");
        
        keystrokeData = {
          hold_times: Array(password.length).fill(1.0),
          flight_times: Array(password.length - 1).fill(0.0),
          latencies: Array(password.length - 1).fill(1.0),
          typing_speed: 100.0,
          backspace_count: 0,
          error_rate: 0.0
        };

        payload = {
          email: targetUser,
          password: password,
          keystroke_data: keystrokeData,
          simulation_type: "CredentialStuffing"
        };
        
        const response = await fetch(url, {
          method: "POST",
          headers: { "Content-Type": "application/json" },
          body: JSON.stringify(payload)
        });
        
        const data = await response.json();
        handleApiResponse(response, data);

      } else if (attackType === "bot") {
        // --- 2. BOT ATTACK (Perfect Uniform Timings) ---
        addLog("Spawning automated webbot typing script...");
        addLog("Generating uniform timings: holds = 50ms, flights = 50ms, std dev = 0.0ms");
        
        keystrokeData = {
          hold_times: Array(password.length).fill(50.0),
          flight_times: Array(password.length - 1).fill(50.0),
          latencies: Array(password.length - 1).fill(100.0),
          typing_speed: 10.0,
          backspace_count: 0,
          error_rate: 0.0
        };

        payload = {
          email: targetUser,
          password: password,
          keystroke_data: keystrokeData,
          simulation_type: "Bot"
        };

        const response = await fetch(url, {
          method: "POST",
          headers: { "Content-Type": "application/json" },
          body: JSON.stringify(payload)
        });
        
        const data = await response.json();
        handleApiResponse(response, data);

      } else if (attackType === "brute") {
        // --- 3. BRUTE FORCE LOCKOUT ---
        addLog("Launching multi-threaded dictionary brute force attack...");
        addLog("Performing 5 consecutive wrong password credentials attempts...");
        
        let lockedOut = false;
        let responseData: any = {};
        let lastResp: any = {};

        for (let i = 1; i <= 5; i++) {
          addLog(`Attempt #${i}: Guessing password "HackPass_${i}"`);
          
          const fakeKeystrokes = {
            hold_times: Array(10).fill(100.0),
            flight_times: Array(9).fill(150.0),
            latencies: Array(9).fill(250.0),
            typing_speed: 4.5,
            backspace_count: 0,
            error_rate: 0.0
          };

          const resp = await fetch(url, {
            method: "POST",
            headers: { "Content-Type": "application/json" },
            body: JSON.stringify({
              email: targetUser,
              password: `HackPass_${i}`,
              keystroke_data: fakeKeystrokes,
              simulation_type: "BruteForce"
            })
          });
          
          lastResp = resp;
          responseData = await resp.json();
          
          if (resp.status === 423) {
            lockedOut = true;
            addLog(`[ALERT] Target Account Locked out at Attempt #${i}!`);
            break;
          }
        }
        
        handleApiResponse(lastResp, responseData);

      } else if (attackType === "impersonate") {
        // --- 4. IMPERSONATION ATTACK (Timing Cadence Mismatch) ---
        addLog("Simulating human impersonator who knows password...");
        addLog("Generating mismatched cadence profile: holds = 220ms, flights = 400ms (slow/hesitant typist)");
        
        keystrokeData = {
          hold_times: Array(password.length).fill(220.0),
          flight_times: Array(password.length - 1).fill(400.0),
          latencies: Array(password.length - 1).fill(620.0),
          typing_speed: 1.6,
          backspace_count: 2,
          error_rate: 0.15
        };

        payload = {
          email: targetUser,
          password: password,
          keystroke_data: keystrokeData,
          simulation_type: "Impersonation"
        };

        const response = await fetch(url, {
          method: "POST",
          headers: { "Content-Type": "application/json" },
          body: JSON.stringify(payload)
        });
        
        const data = await response.json();
        handleApiResponse(response, data);
      }
      
    } catch (err: any) {
      addLog(`SYSTEM FATAL: Connection failed to backend API server at localhost:8080.`);
      setResult({
        status: false,
        statusCode: 500,
        riskScore: 100.0,
        riskLevel: "High",
        anomalies: ["Internal service endpoint offline"],
        details: "FastAPI local server is not running on port 8080."
      });
    } finally {
      setLoading(false);
    }
  };

  const handleApiResponse = (response: Response, data: any) => {
    addLog(`HTTP Server response received: STATUS ${response.status}`);
    
    if (response.ok) {
      addLog("Authentication SUCCESS! Access granted.");
      setResult({
        status: true,
        statusCode: response.status,
        riskScore: data.risk_score || 10,
        riskLevel: data.risk_level || "Low",
        anomalies: data.anomalies || [],
        details: "The timing signature matches the verified baseline parameters. No critical threat flagged."
      });
    } else {
      addLog(`Authentication BLOCKED! Decision: Access Denied.`);
      
      const errorMsg = data.detail?.message || data.detail || "Unauthorized access";
      const anomalies = data.detail?.anomalies || data.anomalies || [];
      const score = data.detail?.risk_score || data.risk_score || 100.0;
      
      if (anomalies.length > 0) {
        anomalies.forEach((anom: string) => addLog(`[ANOMALY TRIGGERED] ${anom}`));
      }
      addLog(`[ALERT] Risk Assessment level: HIGH. Terminating session.`);

      setResult({
        status: false,
        statusCode: response.status,
        riskScore: score,
        riskLevel: "High",
        anomalies: anomalies,
        details: errorMsg
      });
    }
  };

  return (
    <div className="max-w-7xl mx-auto px-4 sm:px-6 lg:px-8 py-12 flex-grow">
      {/* Title */}
      <div className="mb-10 text-center md:text-left">
        <h1 className="text-3xl font-extrabold text-slate-100 flex items-center justify-center md:justify-start gap-2">
          <Terminal className="w-8 h-8 text-cyan-400" />
          Cyberattack Simulation Lab
        </h1>
        <p className="text-xs text-slate-400 mt-1.5">
          Execute simulated network attacks and timing hijack profiles to inspect how behavioral biometrics provides Zero Trust access security
        </p>
      </div>

      {/* Simulator Workspace */}
      <div className="grid grid-cols-1 lg:grid-cols-12 gap-8">
        {/* Left: Controls */}
        <div className="lg:col-span-4 space-y-6">
          <div className="glass-panel p-6 rounded-xl">
            <h3 className="text-sm font-bold text-slate-200 uppercase tracking-wide mb-4">Attack Parameters</h3>
            
            {/* Target Account Select */}
            <div className="mb-4">
              <label className="block text-xs text-slate-405 font-medium mb-1.5">Target Account</label>
              <select
                value={targetUser}
                onChange={(e) => setTargetUser(e.target.value)}
                className="w-full bg-slate-900 border border-slate-800 rounded-lg px-3 py-2 text-sm text-slate-200 focus:outline-none focus:border-indigo-500 cursor-pointer"
              >
                <option value="john@banking.com">John Doe (john@banking.com)</option>
                <option value="jane@banking.com">Jane Smith (jane@banking.com)</option>
                <option value="admin@banking.com">Administrator (admin@banking.com)</option>
              </select>
            </div>

            {/* Attack Type Options */}
            <div className="mb-6">
              <label className="block text-xs text-slate-405 font-medium mb-2">Simulated Attack Vector</label>
              <div className="space-y-2">
                {[
                  { id: "paste", label: "Credential Stuffing (Paste)", desc: "Password pasted instantly by script" },
                  { id: "bot", label: "Uniform Robotic Bot", desc: "Types with perfectly static intervals" },
                  { id: "impersonate", label: "Impersonator Mismatch", desc: "Correct password manually typed with wrong rhythm" },
                  { id: "brute", label: "Brute Force Lockout", desc: "Repeated quick wrong guesses to trigger lockout" }
                ].map(opt => (
                  <label
                    key={opt.id}
                    className={`flex items-start p-3 rounded-lg border cursor-pointer transition-colors ${
                      attackType === opt.id
                        ? "bg-indigo-950/20 border-indigo-500/50"
                        : "bg-slate-900/60 border-slate-800/80 hover:bg-slate-900"
                    }`}
                  >
                    <input
                      type="radio"
                      name="attack-type"
                      checked={attackType === opt.id}
                      onChange={() => setAttackType(opt.id)}
                      className="mt-1 mr-3 text-indigo-600 focus:ring-indigo-500"
                    />
                    <div>
                      <span className="text-xs font-bold text-slate-200 block">{opt.label}</span>
                      <span className="text-[10px] text-slate-405 mt-0.5 block">{opt.desc}</span>
                    </div>
                  </label>
                ))}
              </div>
            </div>

            {/* Execute Button */}
            <button
              onClick={runSimulation}
              disabled={loading}
              className="w-full btn-cyber-primary text-white text-sm font-semibold py-3 rounded-lg flex items-center justify-center gap-2 cursor-pointer disabled:opacity-50"
            >
              {loading ? (
                <RefreshCw className="w-4 h-4 animate-spin" />
              ) : (
                <Play className="w-4 h-4" />
              )}
              Execute Attack Profile
            </button>
          </div>
        </div>

        {/* Right: Console & Results */}
        <div className="lg:col-span-8 flex flex-col gap-6">
          {/* Terminal Console Logs */}
          <div className="glass-panel rounded-xl flex-grow flex flex-col overflow-hidden min-h-[250px] border-cyan-800/25">
            <div className="bg-slate-900 px-4 py-2 border-b border-slate-800/80 flex items-center justify-between">
              <span className="text-[11px] font-mono text-cyan-400 font-bold uppercase tracking-wider flex items-center gap-1.5">
                <Terminal className="w-3.5 h-3.5" />
                Aegis Biometrics Threat Intel Terminal
              </span>
              <span className="w-2.5 h-2.5 rounded-full bg-cyan-400 animate-pulse" />
            </div>
            
            <div className="p-4 font-mono text-xs text-slate-300 space-y-1.5 bg-slate-950 flex-grow overflow-y-auto max-h-[300px]">
              {consoleLogs.map((log, idx) => (
                <div key={idx} className={log.includes("[ALERT]") || log.includes("BLOCKED!") ? "text-rose-400" : log.includes("ANOMALY") ? "text-yellow-400" : "text-slate-350"}>
                  {log}
                </div>
              ))}
              {loading && <div className="text-cyan-400 animate-pulse">Running simulation diagnostics...</div>}
              {consoleLogs.length === 0 && !loading && (
                <div className="text-slate-500 italic">Console idle. Select parameters and click execute.</div>
              )}
            </div>
          </div>

          {/* Biometrics Threat Assessment Result */}
          {result && (
            <div className={`p-6 rounded-xl border flex flex-col md:flex-row gap-6 ${
              result.status 
                ? "bg-emerald-950/20 border-emerald-500/30" 
                : "bg-rose-950/20 border-rose-500/30"
            }`}>
              {/* Left Column: Icon & Score badge */}
              <div className="flex flex-col items-center justify-center md:border-r md:border-slate-800 md:pr-6 text-center">
                {result.status ? (
                  <div className="w-12 h-12 bg-emerald-950/50 border border-emerald-500/40 rounded-full flex items-center justify-center text-emerald-400 mb-3 pulse-teal">
                    <ShieldCheck className="w-7 h-7" />
                  </div>
                ) : (
                  <div className="w-12 h-12 bg-rose-950/50 border border-rose-500/40 rounded-full flex items-center justify-center text-rose-450 mb-3 animate-pulse">
                    <ShieldAlert className="w-7 h-7" />
                  </div>
                )}
                
                <span className="text-[10px] text-slate-405 uppercase font-bold tracking-wider mb-0.5">Risk Score</span>
                <span className={`text-3xl font-extrabold ${result.status ? "text-emerald-400" : "text-rose-450"}`}>
                  {result.riskScore}%
                </span>
                <span className={`text-xs font-semibold px-2 py-0.5 rounded mt-1.5 uppercase ${
                  result.riskLevel === "Low" ? "bg-emerald-900/40 text-emerald-400" : "bg-rose-900/40 text-rose-400"
                }`}>
                  {result.riskLevel} Risk
                </span>
              </div>

              {/* Right Column: Threats & Details */}
              <div className="flex-grow">
                <h4 className="text-base font-bold text-slate-100 mb-1 flex items-center gap-1.5">
                  {result.status ? "Authentication Granted" : "Threat Intercepted / Access Blocked"}
                  <span className="text-xs text-slate-500 font-mono">(HTTP {result.statusCode})</span>
                </h4>
                <p className="text-xs text-slate-400 mb-4">{result.details}</p>
                
                {result.anomalies.length > 0 && (
                  <div>
                    <h5 className="text-xs font-bold text-slate-200 mb-1.5 uppercase tracking-wide flex items-center gap-1">
                      <AlertTriangle className="w-3.5 h-3.5 text-yellow-500" />
                      Anomalies Flagged:
                    </h5>
                    <div className="grid grid-cols-1 sm:grid-cols-2 gap-2">
                      {result.anomalies.map((anom, idx) => (
                        <div key={idx} className="p-2 bg-slate-900/60 border border-slate-800 rounded text-[10px] text-slate-300 font-mono">
                          • {anom}
                        </div>
                      ))}
                    </div>
                  </div>
                )}
              </div>
            </div>
          )}
        </div>
      </div>
    </div>
  );
}
