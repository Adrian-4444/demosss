"use client";

import React, { useState, useEffect } from "react";
import { useRouter } from "next/navigation";
import { Line, Bar } from "react-chartjs-2";
import {
  Chart as ChartJS,
  CategoryScale,
  LinearScale,
  PointElement,
  LineElement,
  BarElement,
  Title,
  Tooltip,
  Legend,
  Filler
} from "chart.js";
import { ShieldCheck, ShieldAlert, Key, User, Activity, Clock, FileText, ChevronRight, HelpCircle, Check } from "lucide-react";

// Register ChartJS modules
ChartJS.register(
  CategoryScale,
  LinearScale,
  PointElement,
  LineElement,
  BarElement,
  Title,
  Tooltip,
  Legend,
  Filler
);

interface AuditLog {
  id: number;
  timestamp: string;
  status: boolean;
  similarity_score: number | null;
  confidence_score: number | null;
  risk_score: number | null;
  risk_level: string | null;
  flagged_anomalies: string | null;
  user_agent: string | null;
  client_ip: string | null;
  simulation_type: string;
}

export default function UserDashboard() {
  const router = useRouter();
  
  const [loading, setLoading] = useState(true);
  const [stats, setStats] = useState<{
    total_logins: number;
    failed_logins: number;
    avg_speed: number;
    avg_hold: number;
    avg_similarity: number;
    history: AuditLog[];
  } | null>(null);
  
  const [error, setError] = useState("");
  const [email, setEmail] = useState("");
  const [username, setUsername] = useState("");

  useEffect(() => {
    const token = localStorage.getItem("token");
    const storedEmail = localStorage.getItem("email") || "";
    const storedName = localStorage.getItem("username") || "";
    
    setEmail(storedEmail);
    setUsername(storedName);

    if (!token) {
      router.push("/login");
      return;
    }

    const fetchStats = async () => {
      try {
        const response = await fetch("http://localhost:8080/api/dashboard/user-stats", {
          headers: {
            "Authorization": `Bearer ${token}`
          }
        });

        if (!response.ok) {
          if (response.status === 401) {
            localStorage.clear();
            router.push("/login");
            return;
          }
          throw new Error("Failed to load user biometrics stats");
        }

        const data = await response.json();
        setStats(data);
      } catch (err: any) {
        setError(err.message || "An error occurred fetching dashboard data.");
      } finally {
        setLoading(false);
      }
    };

    fetchStats();
  }, [router]);

  if (loading) {
    return (
      <div className="flex-grow flex items-center justify-center text-slate-400 text-sm">
        <Activity className="w-5 h-5 animate-spin mr-2 text-cyan-400" />
        Loading biometric session profiles...
      </div>
    );
  }

  if (error || !stats) {
    return (
      <div className="max-w-md w-full mx-auto my-12 p-8 glass-panel text-center">
        <ShieldAlert className="w-12 h-12 text-rose-500 mx-auto mb-4" />
        <h3 className="text-lg font-bold text-slate-200">Dashboard Unavailable</h3>
        <p className="text-xs text-slate-455 mt-2">{error || "Failed to retrieve session metrics."}</p>
        <button
          onClick={() => window.location.reload()}
          className="mt-6 btn-cyber-primary text-white text-xs font-semibold px-4 py-2 rounded-lg cursor-pointer"
        >
          Retry Connection
        </button>
      </div>
    );
  }

  // --- CHART CONFIGURATIONS ---

  // 1. Similarity Trend Chart (Line)
  const lineLogs = [...stats.history].reverse().filter(log => log.similarity_score !== null);
  const similarityChartData = {
    labels: lineLogs.map((_, idx) => `Login #${idx + 1}`),
    datasets: [
      {
        label: "Biometric Similarity Score (%)",
        data: lineLogs.map(log => log.similarity_score),
        borderColor: "#6366f1",
        backgroundColor: "rgba(99, 102, 241, 0.1)",
        fill: true,
        tension: 0.3,
        pointBackgroundColor: "#06b6d4",
        pointBorderColor: "#fff",
      }
    ]
  };

  const similarityChartOptions = {
    responsive: true,
    maintainAspectRatio: false,
    plugins: {
      legend: { display: false },
      tooltip: {
        callbacks: {
          label: (context: any) => `Similarity: ${context.parsed.y.toFixed(1)}%`
        }
      }
    },
    scales: {
      y: { min: 0, max: 100, grid: { color: "rgba(255, 255, 255, 0.05)" }, ticks: { color: "#94a3b8" } },
      x: { grid: { display: false }, ticks: { color: "#94a3b8" } }
    }
  };

  // 2. Mock Hold times distribution for password chars
  // In a production app, these would come from baseline_stats.
  // For seed data, John Doe's password is "SecureJohn99" (length 12).
  // We extract his baseline mean holds or generate placeholders if baseline statistics are missing.
  const baselineHoldTimes = [95, 110, 85, 120, 105, 90, 130, 95, 115, 100, 140, 125];
  const baselineLabels = ["S", "e", "c", "u", "r", "e", "J", "o", "h", "n", "9", "9"];

  const holdTimesChartData = {
    labels: baselineLabels,
    datasets: [
      {
        label: "Baseline Key Hold Time (ms)",
        data: baselineHoldTimes,
        backgroundColor: "rgba(6, 182, 212, 0.65)",
        borderColor: "#06b6d4",
        borderWidth: 1.5,
        borderRadius: 4
      }
    ]
  };

  const holdTimesChartOptions = {
    responsive: true,
    maintainAspectRatio: false,
    plugins: { legend: { display: false } },
    scales: {
      y: { grid: { color: "rgba(255, 255, 255, 0.05)" }, ticks: { color: "#94a3b8" } },
      x: { grid: { display: false }, ticks: { color: "#94a3b8" } }
    }
  };

  return (
    <div className="max-w-7xl mx-auto px-4 sm:px-6 lg:px-8 py-12 flex-grow">
      {/* Welcome header */}
      <div className="mb-10 text-center md:text-left">
        <h1 className="text-3xl font-extrabold text-slate-100 flex items-center justify-center md:justify-start gap-2">
          <ShieldCheck className="w-8 h-8 text-cyan-400 animate-pulse" />
          User Biometric Operations Center
        </h1>
        <p className="text-xs text-slate-400 mt-1.5">
          Active Profile: <strong className="text-slate-200">{username}</strong> ({email})
        </p>
      </div>

      {/* Summary Scorecard Cards */}
      <div className="grid grid-cols-2 lg:grid-cols-4 gap-4 mb-8">
        <div className="glass-panel p-5 rounded-xl border-l-4 border-l-indigo-500">
          <span className="text-[10px] uppercase font-bold text-slate-400 tracking-wider">Avg Typing Speed</span>
          <h3 className="text-2xl font-extrabold text-slate-100 mt-1 flex items-baseline gap-1">
            {stats.avg_speed}
            <span className="text-xs text-slate-400 font-normal">keys/sec</span>
          </h3>
        </div>

        <div className="glass-panel p-5 rounded-xl border-l-4 border-l-cyan-500">
          <span className="text-[10px] uppercase font-bold text-slate-400 tracking-wider">Avg Key Hold Time</span>
          <h3 className="text-2xl font-extrabold text-slate-100 mt-1 flex items-baseline gap-1">
            {stats.avg_hold.toFixed(1)}
            <span className="text-xs text-slate-400 font-normal">ms</span>
          </h3>
        </div>

        <div className="glass-panel p-5 rounded-xl border-l-4 border-l-emerald-500">
          <span className="text-[10px] uppercase font-bold text-slate-400 tracking-wider">Avg Typing Consistency</span>
          <h3 className="text-2xl font-extrabold text-slate-100 mt-1 flex items-baseline gap-1">
            {stats.avg_similarity.toFixed(1)}
            <span className="text-xs text-slate-400 font-normal">%</span>
          </h3>
        </div>

        <div className="glass-panel p-5 rounded-xl border-l-4 border-l-rose-500">
          <span className="text-[10px] uppercase font-bold text-slate-400 tracking-wider">Security Blocks</span>
          <h3 className="text-2xl font-extrabold text-slate-100 mt-1">
            {stats.failed_logins}
            <span className="text-xs text-slate-400 font-normal ml-1">threats stopped</span>
          </h3>
        </div>
      </div>

      {/* Main Charts Row */}
      <div className="grid grid-cols-1 lg:grid-cols-2 gap-8 mb-10">
        {/* Similarity Line Chart */}
        <div className="glass-panel p-6 rounded-xl">
          <h3 className="text-sm font-bold text-slate-200 uppercase tracking-wide mb-4 flex items-center gap-1.5">
            <Activity className="w-4 h-4 text-indigo-400" />
            Typing Rhythm Consistency Trend
          </h3>
          <div className="h-64 relative">
            <Line data={similarityChartData} options={similarityChartOptions} />
          </div>
        </div>

        {/* Hold Times Bar Chart */}
        <div className="glass-panel p-6 rounded-xl border-cyan-800/20">
          <h3 className="text-sm font-bold text-slate-200 uppercase tracking-wide mb-4 flex items-center gap-1.5">
            <Clock className="w-4 h-4 text-cyan-400" />
            Key Press Hold Time Signature
          </h3>
          <div className="h-64 relative">
            <Bar data={holdTimesChartData} options={holdTimesChartOptions} />
          </div>
        </div>
      </div>

      {/* Audit History Logs Table */}
      <div className="glass-panel rounded-xl overflow-hidden border-slate-800/80 mb-6">
        <div className="px-6 py-4 bg-slate-900/60 border-b border-slate-850 flex items-center gap-2">
          <FileText className="w-4 h-4 text-indigo-400" />
          <h3 className="text-sm font-bold text-slate-200 uppercase tracking-wider">Biometric Audit Trail Logs</h3>
        </div>

        <div className="overflow-x-auto">
          <table className="w-full text-left text-xs border-collapse">
            <thead>
              <tr className="bg-slate-950/60 text-slate-400 border-b border-slate-900">
                <th className="px-6 py-3 font-semibold uppercase tracking-wider">Timestamp</th>
                <th className="px-6 py-3 font-semibold uppercase tracking-wider">Status</th>
                <th className="px-6 py-3 font-semibold uppercase tracking-wider">Similarity</th>
                <th className="px-6 py-3 font-semibold uppercase tracking-wider">AI Confidence</th>
                <th className="px-6 py-3 font-semibold uppercase tracking-wider">Risk Level</th>
                <th className="px-6 py-3 font-semibold uppercase tracking-wider">Access IP</th>
                <th className="px-6 py-3 font-semibold uppercase tracking-wider">Anomalies Detected</th>
              </tr>
            </thead>
            <tbody className="divide-y divide-slate-850">
              {stats.history.map((log) => {
                const anomalies = log.flagged_anomalies ? JSON.parse(log.flagged_anomalies) : [];
                return (
                  <tr key={log.id} className="hover:bg-slate-900/20 transition-colors">
                    <td className="px-6 py-3.5 whitespace-nowrap text-slate-350">
                      {new Date(log.timestamp).toLocaleString()}
                    </td>
                    <td className="px-6 py-3.5 whitespace-nowrap">
                      {log.status ? (
                        <span className="inline-flex items-center gap-1 text-[10px] font-semibold text-emerald-450 bg-emerald-950/20 px-2 py-0.5 rounded border border-emerald-900/30">
                          <Check className="w-3 h-3" />
                          SUCCESS
                        </span>
                      ) : (
                        <span className="inline-flex items-center gap-1 text-[10px] font-semibold text-rose-450 bg-rose-950/20 px-2 py-0.5 rounded border border-rose-900/30">
                          <ShieldAlert className="w-3 h-3" />
                          BLOCKED
                        </span>
                      )}
                    </td>
                    <td className="px-6 py-3.5 whitespace-nowrap font-mono text-slate-200">
                      {log.similarity_score !== null ? `${log.similarity_score.toFixed(1)}%` : "—"}
                    </td>
                    <td className="px-6 py-3.5 whitespace-nowrap font-mono text-slate-200">
                      {log.confidence_score !== null ? `${log.confidence_score.toFixed(1)}%` : "—"}
                    </td>
                    <td className="px-6 py-3.5 whitespace-nowrap">
                      <span className={`text-[10px] font-bold uppercase ${
                        log.risk_level === "Low" 
                          ? "text-emerald-400" 
                          : log.risk_level === "Medium"
                            ? "text-yellow-400"
                            : "text-rose-400"
                      }`}>
                        {log.risk_level || "Low"}
                      </span>
                    </td>
                    <td className="px-6 py-3.5 whitespace-nowrap font-mono text-slate-400">{log.client_ip}</td>
                    <td className="px-6 py-3.5 text-slate-400 leading-relaxed max-w-xs truncate" title={anomalies.join(", ")}>
                      {anomalies.length > 0 ? anomalies.join(", ") : <span className="text-slate-600">None</span>}
                    </td>
                  </tr>
                );
              })}
            </tbody>
          </table>
        </div>
      </div>
    </div>
  );
}
