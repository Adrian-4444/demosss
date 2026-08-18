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
import { ShieldCheck, ShieldAlert, Cpu, Activity, Users, Radio, Terminal, AlertTriangle, Layers, Award } from "lucide-react";

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

interface PerformanceMetric {
  accuracy: number;
  precision: number;
  recall: number;
  f1_score: number;
  far: number;
  frr: number;
  eer: number;
  confusion_matrix: { tn: number; fp: number; fn: number; tp: number };
  roc_curve: { fpr: number[]; tpr: number[] };
}

export default function AdminDashboard() {
  const router = useRouter();
  const [loading, setLoading] = useState(true);
  const [stats, setStats] = useState<{
    total_users: number;
    total_attempts: number;
    failed_attempts: number;
    compromised_prevented: number;
    daily_logins: { date: string; success: number; failed: number }[];
    anomalies_distribution: { name: string; value: number }[];
    recent_attempts: AuditLog[];
  } | null>(null);

  const [mlComparisons, setMlComparisons] = useState<Dict<PerformanceMetric> | null>(null);
  const [selectedAlgo, setSelectedAlgo] = useState("Random Forest");
  const [activeModelName, setActiveModelName] = useState("");
  const [error, setError] = useState("");

  useEffect(() => {
    const token = localStorage.getItem("token");
    const role = localStorage.getItem("role");

    if (!token || role !== "admin") {
      router.push("/login");
      return;
    }

    const fetchData = async () => {
      try {
        // Fetch dashboard statistics
        const statsResponse = await fetch("http://localhost:8080/api/dashboard/admin-stats", {
          headers: { "Authorization": `Bearer ${token}` }
        });

        if (!statsResponse.ok) {
          throw new Error("Failed to load admin stats");
        }
        const statsData = await statsResponse.json();
        setStats(statsData);

        // Fetch ML models comparisons
        const mlResponse = await fetch("http://localhost:8080/api/ml/compare-models", {
          headers: { "Authorization": `Bearer ${token}` }
        });

        if (mlResponse.ok) {
          const mlData = await mlResponse.json();
          setMlComparisons(mlData.comparisons);
          setActiveModelName(mlData.active_model);
          setSelectedAlgo(mlData.active_model);
        }
      } catch (err: any) {
        setError(err.message || "An error occurred fetching dashboard metrics.");
      } finally {
        setLoading(false);
      }
    };

    fetchData();
  }, [router]);

  if (loading) {
    return (
      <div className="flex-grow flex items-center justify-center text-slate-400 text-sm">
        <Activity className="w-5 h-5 animate-spin mr-2 text-cyan-400" />
        Retrieving system biometrics audit databases...
      </div>
    );
  }

  if (error || !stats) {
    return (
      <div className="max-w-md w-full mx-auto my-12 p-8 glass-panel text-center">
        <ShieldAlert className="w-12 h-12 text-rose-500 mx-auto mb-4" />
        <h3 className="text-lg font-bold text-slate-200">System Dashboard Offline</h3>
        <p className="text-xs text-slate-455 mt-2">{error || "Failed to load corporate telemetry."}</p>
        <button
          onClick={() => window.location.reload()}
          className="mt-6 btn-cyber-primary text-white text-xs font-semibold px-4 py-2 rounded-lg cursor-pointer"
        >
          Reconnect
        </button>
      </div>
    );
  }

  // --- CHART CONFIGURATIONS ---

  // 1. Daily Login volume timeline
  const dailyChartData = {
    labels: stats.daily_logins.map(d => d.date),
    datasets: [
      {
        label: "Successful Logins",
        data: stats.daily_logins.map(d => d.success),
        borderColor: "#10b981",
        backgroundColor: "rgba(16, 185, 129, 0.05)",
        fill: true,
        tension: 0.2
      },
      {
        label: "Blocked Logins (Threats)",
        data: stats.daily_logins.map(d => d.failed),
        borderColor: "#f43f5e",
        backgroundColor: "rgba(244, 63, 94, 0.05)",
        fill: true,
        tension: 0.2
      }
    ]
  };

  const dailyChartOptions = {
    responsive: true,
    maintainAspectRatio: false,
    plugins: { legend: { labels: { color: "#94a3b8" } } },
    scales: {
      y: { grid: { color: "rgba(255, 255, 255, 0.05)" }, ticks: { color: "#94a3b8" } },
      x: { grid: { display: false }, ticks: { color: "#94a3b8" } }
    }
  };

  // 2. Anomaly distribution chart
  const anomalyChartData = {
    labels: stats.anomalies_distribution.map(a => a.name),
    datasets: [
      {
        label: "Incident Frequency",
        data: stats.anomalies_distribution.map(a => a.value),
        backgroundColor: "rgba(99, 102, 241, 0.65)",
        borderColor: "#6366f1",
        borderWidth: 1,
        borderRadius: 4
      }
    ]
  };

  const anomalyChartOptions = {
    responsive: true,
    maintainAspectRatio: false,
    plugins: { legend: { display: false } },
    scales: {
      y: { grid: { color: "rgba(255, 255, 255, 0.05)" }, ticks: { color: "#94a3b8" } },
      x: { grid: { display: false }, ticks: { color: "#94a3b8", font: { size: 9 } } }
    }
  };

  // 3. ML Models validation comparison chart
  let mlChartData = null;
  if (mlComparisons) {
    mlChartData = {
      labels: Object.keys(mlComparisons),
      datasets: [
        {
          label: "Validation Accuracy (%)",
          data: Object.values(mlComparisons).map(m => m.accuracy),
          backgroundColor: "rgba(6, 182, 212, 0.65)",
          borderColor: "#06b6d4",
          borderWidth: 1
        },
        {
          label: "F1 Score (%)",
          data: Object.values(mlComparisons).map(m => m.f1_score),
          backgroundColor: "rgba(99, 102, 241, 0.65)",
          borderColor: "#6366f1",
          borderWidth: 1
        }
      ]
    };
  }

  const selectedMetric = mlComparisons ? mlComparisons[selectedAlgo] : null;

  return (
    <div className="max-w-7xl mx-auto px-4 sm:px-6 lg:px-8 py-12 flex-grow">
      {/* Title */}
      <div className="mb-10 text-center md:text-left flex flex-col md:flex-row items-center justify-between gap-4">
        <div>
          <h1 className="text-3xl font-extrabold text-slate-100 flex items-center justify-center md:justify-start gap-2">
            <Radio className="w-8 h-8 text-cyan-400" />
            Cybersecurity Command Operations Center
          </h1>
          <p className="text-xs text-slate-400 mt-1.5">
            Real-time biometric analytics, threat patterns, and machine learning models dashboard
          </p>
        </div>
        <div className="inline-flex items-center gap-2 px-3.5 py-1.5 rounded-full bg-slate-900 border border-slate-800 text-xs font-semibold text-slate-350 font-mono">
          <Cpu className="w-4 h-4 text-cyan-400" />
          ACTIVE CLASSIFIER: <strong className="text-cyan-400">{activeModelName || "None"}</strong>
        </div>
      </div>

      {/* Summary Scorecard Grid */}
      <div className="grid grid-cols-2 lg:grid-cols-4 gap-4 mb-8">
        <div className="glass-panel p-5 rounded-xl border-l-4 border-l-cyan-500">
          <span className="text-[10px] uppercase font-bold text-slate-400 tracking-wider">Total Users Enrolled</span>
          <h3 className="text-2xl font-extrabold text-slate-100 mt-1 flex items-center gap-2">
            <Users className="w-5 h-5 text-cyan-400" />
            {stats.total_users}
          </h3>
        </div>

        <div className="glass-panel p-5 rounded-xl border-l-4 border-l-indigo-500">
          <span className="text-[10px] uppercase font-bold text-slate-400 tracking-wider">Total Authentication Requests</span>
          <h3 className="text-2xl font-extrabold text-slate-100 mt-1 flex items-center gap-2">
            <Activity className="w-5 h-5 text-indigo-400" />
            {stats.total_attempts}
          </h3>
        </div>

        <div className="glass-panel p-5 rounded-xl border-l-4 border-l-rose-500">
          <span className="text-[10px] uppercase font-bold text-slate-400 tracking-wider">Blocked Failures</span>
          <h3 className="text-2xl font-extrabold text-slate-100 mt-1 flex items-center gap-2">
            <ShieldAlert className="w-5 h-5 text-rose-500" />
            {stats.failed_attempts}
          </h3>
        </div>

        <div className="glass-panel p-5 rounded-xl border-l-4 border-l-emerald-500">
          <span className="text-[10px] uppercase font-bold text-slate-400 tracking-wider">Credential Compromises Prevented</span>
          <h3 className="text-2xl font-extrabold text-slate-100 mt-1 flex items-center gap-2">
            <ShieldCheck className="w-5 h-5 text-emerald-400" />
            {stats.compromised_prevented}
          </h3>
        </div>
      </div>

      {/* Daily Volume and Anomaly Distribution Row */}
      <div className="grid grid-cols-1 lg:grid-cols-12 gap-8 mb-10">
        {/* Timeline Log */}
        <div className="glass-panel p-6 rounded-xl lg:col-span-7">
          <h3 className="text-sm font-bold text-slate-200 uppercase tracking-wide mb-4 flex items-center gap-1.5">
            <Activity className="w-4 h-4 text-indigo-400" />
            Authentication Daily Volume Timeline
          </h3>
          <div className="h-64 relative">
            <Line data={dailyChartData} options={dailyChartOptions} />
          </div>
        </div>

        {/* Anomaly Distribution Chart */}
        <div className="glass-panel p-6 rounded-xl lg:col-span-5 border-cyan-800/20">
          <h3 className="text-sm font-bold text-slate-200 uppercase tracking-wide mb-4 flex items-center gap-1.5">
            <AlertTriangle className="w-4 h-4 text-cyan-400" />
            Flagged Anomaly Signature Distribution
          </h3>
          <div className="h-64 relative">
            <Bar data={anomalyChartData} options={anomalyChartOptions} />
          </div>
        </div>
      </div>

      {/* Machine Learning Models Performance Comparison Sandbox */}
      {mlComparisons && (
        <div className="glass-panel p-6 rounded-xl border-indigo-900/30 mb-10">
          <div className="mb-6 flex flex-col sm:flex-row sm:items-center justify-between gap-4 border-b border-slate-800 pb-4">
            <div>
              <h3 className="text-sm font-extrabold text-slate-100 uppercase tracking-wider flex items-center gap-2">
                <Layers className="w-5 h-5 text-indigo-400" />
                AI Model Comparison Panel
              </h3>
              <p className="text-[11px] text-slate-400 mt-0.5">Evaluate the accuracy, error rates, and confusion matrices across 7 machine learning models</p>
            </div>
            
            {/* Algorithm Select */}
            <div className="flex items-center gap-2">
              <span className="text-[10px] text-slate-405 uppercase font-bold tracking-wide">Detailed Analysis:</span>
              <select
                value={selectedAlgo}
                onChange={(e) => setSelectedAlgo(e.target.value)}
                className="bg-slate-900 border border-slate-850 rounded px-2.5 py-1 text-xs text-slate-200 focus:outline-none focus:border-indigo-500 cursor-pointer"
              >
                {Object.keys(mlComparisons).map(name => (
                  <option key={name} value={name}>
                    {name} {name === activeModelName ? "(Active)" : ""}
                  </option>
                ))}
              </select>
            </div>
          </div>

          <div className="grid grid-cols-1 lg:grid-cols-12 gap-8">
            {/* Left: Overall Accuracy Bar Chart */}
            <div className="lg:col-span-6 h-64 relative">
              {mlChartData && (
                <Bar 
                  data={mlChartData} 
                  options={{
                    responsive: true,
                    maintainAspectRatio: false,
                    plugins: { legend: { labels: { color: "#94a3b8" } } },
                    scales: {
                      y: { min: 0, max: 100, grid: { color: "rgba(255, 255, 255, 0.05)" }, ticks: { color: "#94a3b8" } },
                      x: { grid: { display: false }, ticks: { color: "#94a3b8" } }
                    }
                  }} 
                />
              )}
            </div>

            {/* Right: Selected Algorithm Performance Detail */}
            {selectedMetric && (
              <div className="lg:col-span-6 grid grid-cols-1 md:grid-cols-12 gap-6">
                {/* Metrics Table details */}
                <div className="md:col-span-7 space-y-2 text-xs">
                  <div className="flex justify-between items-center p-2 rounded bg-slate-900/60 border border-slate-850">
                    <span className="text-slate-405">Accuracy Rating:</span>
                    <strong className="text-cyan-400 font-mono">{selectedMetric.accuracy.toFixed(1)}%</strong>
                  </div>
                  <div className="flex justify-between items-center p-2 rounded bg-slate-900/60 border border-slate-850">
                    <span className="text-slate-405">F1-Score:</span>
                    <strong className="text-indigo-400 font-mono">{selectedMetric.f1_score.toFixed(1)}%</strong>
                  </div>
                  <div className="flex justify-between items-center p-2 rounded bg-slate-900/60 border border-slate-850">
                    <span className="text-slate-405">False Acceptance Rate (FAR):</span>
                    <strong className="text-rose-400 font-mono">{selectedMetric.far.toFixed(1)}%</strong>
                  </div>
                  <div className="flex justify-between items-center p-2 rounded bg-slate-900/60 border border-slate-850">
                    <span className="text-slate-405">False Rejection Rate (FRR):</span>
                    <strong className="text-yellow-405 font-mono">{selectedMetric.frr.toFixed(1)}%</strong>
                  </div>
                  <div className="flex justify-between items-center p-2 rounded bg-indigo-950/20 border border-indigo-900/30">
                    <span className="text-indigo-350 font-semibold">Equal Error Rate (EER):</span>
                    <strong className="text-emerald-400 font-mono">{selectedMetric.eer.toFixed(1)}%</strong>
                  </div>
                </div>

                {/* Confusion Matrix Visualization */}
                <div className="md:col-span-5 flex flex-col justify-center">
                  <div className="text-[10px] text-center font-bold text-slate-405 uppercase tracking-wide mb-2">Confusion Matrix</div>
                  <div className="grid grid-cols-2 gap-1 font-mono text-[10px] text-center text-slate-300">
                    {/* TN */}
                    <div className="p-3 bg-slate-900/60 border border-slate-800/80 rounded">
                      <div className="text-slate-500 font-bold mb-0.5">TN</div>
                      <div className="text-slate-200 text-sm font-extrabold">{selectedMetric.confusion_matrix.tn}</div>
                    </div>
                    {/* FP */}
                    <div className="p-3 bg-rose-950/20 border border-rose-900/30 rounded text-rose-400">
                      <div className="text-rose-450 font-bold mb-0.5">FP (FAR)</div>
                      <div className="text-rose-400 text-sm font-extrabold">{selectedMetric.confusion_matrix.fp}</div>
                    </div>
                    {/* FN */}
                    <div className="p-3 bg-yellow-950/20 border border-yellow-900/30 rounded text-yellow-450">
                      <div className="text-yellow-450 font-bold mb-0.5">FN (FRR)</div>
                      <div className="text-yellow-405 text-sm font-extrabold">{selectedMetric.confusion_matrix.fn}</div>
                    </div>
                    {/* TP */}
                    <div className="p-3 bg-emerald-950/20 border border-emerald-900/30 rounded text-emerald-400">
                      <div className="text-emerald-450 font-bold mb-0.5">TP</div>
                      <div className="text-emerald-400 text-sm font-extrabold">{selectedMetric.confusion_matrix.tp}</div>
                    </div>
                  </div>
                </div>
              </div>
            )}
          </div>
        </div>
      )}

      {/* Global Activity Log Timeline */}
      <div className="glass-panel rounded-xl overflow-hidden border-slate-800/80">
        <div className="px-6 py-4 bg-slate-900/60 border-b border-slate-850 flex items-center gap-2">
          <Terminal className="w-4 h-4 text-indigo-400" />
          <h3 className="text-sm font-bold text-slate-200 uppercase tracking-wider">System-wide Authentication Audit Trail</h3>
        </div>

        <div className="overflow-x-auto">
          <table className="w-full text-left text-xs border-collapse">
            <thead>
              <tr className="bg-slate-950/60 text-slate-400 border-b border-slate-900">
                <th className="px-6 py-3 font-semibold uppercase tracking-wider">Timestamp</th>
                <th className="px-6 py-3 font-semibold uppercase tracking-wider">User ID / Email</th>
                <th className="px-6 py-3 font-semibold uppercase tracking-wider">Status</th>
                <th className="px-6 py-3 font-semibold uppercase tracking-wider">Simulation Type</th>
                <th className="px-6 py-3 font-semibold uppercase tracking-wider">Risk Level</th>
                <th className="px-6 py-3 font-semibold uppercase tracking-wider">IP / Access Network</th>
                <th className="px-6 py-3 font-semibold uppercase tracking-wider">Anomalies Detected</th>
              </tr>
            </thead>
            <tbody className="divide-y divide-slate-850">
              {stats.recent_attempts.map((log) => {
                const anomalies = log.flagged_anomalies ? JSON.parse(log.flagged_anomalies) : [];
                return (
                  <tr key={log.id} className="hover:bg-slate-900/20 transition-colors">
                    <td className="px-6 py-3.5 whitespace-nowrap text-slate-350">
                      {new Date(log.timestamp).toLocaleString()}
                    </td>
                    <td className="px-6 py-3.5 whitespace-nowrap font-semibold text-slate-250">
                      {log.user ? log.user.email : `User_${log.user_id}`}
                    </td>
                    <td className="px-6 py-3.5 whitespace-nowrap">
                      {log.status ? (
                        <span className="inline-flex items-center gap-1 text-[10px] font-semibold text-emerald-450 bg-emerald-950/20 px-2 py-0.5 rounded border border-emerald-900/30">
                          SUCCESS
                        </span>
                      ) : (
                        <span className="inline-flex items-center gap-1 text-[10px] font-semibold text-rose-450 bg-rose-950/20 px-2 py-0.5 rounded border border-rose-900/30">
                          BLOCKED
                        </span>
                      )}
                    </td>
                    <td className="px-6 py-3.5 whitespace-nowrap text-slate-400 font-mono">
                      {log.simulation_type !== "None" ? (
                        <span className="text-yellow-450 font-bold bg-yellow-950/25 px-1.5 py-0.5 rounded border border-yellow-900/30">{log.simulation_type}</span>
                      ) : (
                        <span className="text-slate-500">Standard</span>
                      )}
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
