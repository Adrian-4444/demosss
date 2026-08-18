"use client";

import React, { useState, useEffect } from "react";
import Link from "next/link";
import { usePathname, useRouter } from "next/navigation";
import { Shield, Key, Cpu, User, LogOut, Terminal, Activity, Eye } from "lucide-react";

export default function ClientLayout({ children }: { children: React.ReactNode }) {
  const pathname = usePathname();
  const router = useRouter();

  const [token, setToken] = useState<string | null>(null);
  const [role, setRole] = useState<string | null>(null);
  const [username, setUsername] = useState<string | null>(null);

  // Poll for token changes to update navigation dynamically
  useEffect(() => {
    const checkAuth = () => {
      const storedToken = localStorage.getItem("token");
      const storedRole = localStorage.getItem("role");
      const storedName = localStorage.getItem("username");

      setToken(storedToken);
      setRole(storedRole);
      setUsername(storedName);
    };

    checkAuth();

    // Listen to custom login events or storage changes
    window.addEventListener("storage", checkAuth);
    const interval = setInterval(checkAuth, 1000);

    return () => {
      window.removeEventListener("storage", checkAuth);
      clearInterval(interval);
    };
  }, []);

  const handleLogout = () => {
    localStorage.clear();
    setToken(null);
    setRole(null);
    setUsername(null);
    router.push("/login");
  };

  const isActive = (path: string) => pathname === path;

  return (
    <div className="flex flex-col min-h-screen">
      {/* Top Header */}
      <header className="glass-panel sticky top-0 z-50 border-b border-slate-800">
        <div className="max-w-7xl mx-auto px-4 sm:px-6 lg:px-8">
          <div className="flex items-center justify-between h-16">
            {/* Logo */}
            <div className="flex items-center">
              <Link href="/" className="flex items-center gap-2 text-indigo-400 font-bold text-lg tracking-wide hover:opacity-90">
                <Shield className="w-6 h-6 text-cyan-400" />
                <span className="text-slate-100 font-extrabold uppercase">Key</span>
                <span className="text-cyan-400 font-light lowercase">Dynamics</span>
              </Link>
            </div>

            {/* Navigation links */}
            <nav className="hidden md:flex space-x-1">
              <Link
                href="/"
                className={`px-3 py-2 rounded-md text-sm font-medium transition-colors ${isActive("/")
                  ? "bg-indigo-600/20 text-indigo-400 border-b-2 border-indigo-500"
                  : "text-slate-300 hover:text-white hover:bg-slate-800/40"
                  }`}
              >
                Concept
              </Link>

              <Link
                href="/register"
                className={`px-3 py-2 rounded-md text-sm font-medium transition-colors ${isActive("/register")
                  ? "bg-indigo-600/20 text-indigo-400 border-b-2 border-indigo-500"
                  : "text-slate-300 hover:text-white hover:bg-slate-800/40"
                  }`}
              >
                Enroll Profile
              </Link>

              <Link
                href="/login"
                className={`px-3 py-2 rounded-md text-sm font-medium transition-colors ${isActive("/login")
                  ? "bg-indigo-600/20 text-indigo-400 border-b-2 border-indigo-500"
                  : "text-slate-300 hover:text-white hover:bg-slate-800/40"
                  }`}
              >
                Secure Login
              </Link>

              <Link
                href="/simulations"
                className={`px-3 py-2 rounded-md text-sm font-medium transition-colors flex items-center gap-1.5 ${isActive("/simulations")
                  ? "bg-cyan-600/20 text-cyan-400 border-b-2 border-cyan-500"
                  : "text-slate-300 hover:text-white hover:bg-slate-800/40"
                  }`}
              >
                <Terminal className="w-4 h-4" />
                Attack Center
              </Link>
            </nav>

            {/* Authentication Action / Profile */}
            <div className="flex items-center gap-4">
              {token ? (
                <div className="flex items-center gap-3">
                  <div className="hidden sm:flex flex-col text-right">
                    <span className="text-xs text-slate-400">Authenticated</span>
                    <Link
                      href={role === "admin" ? "/dashboard/admin" : "/dashboard/user"}
                      className="text-sm font-semibold text-indigo-400 hover:underline flex items-center gap-1"
                    >
                      <User className="w-3.5 h-3.5 text-cyan-400" />
                      {username || "User"} ({role})
                    </Link>
                  </div>

                  {/* Dashboard link for quick access */}
                  <Link
                    href={role === "admin" ? "/dashboard/admin" : "/dashboard/user"}
                    className="p-2 rounded-md bg-slate-800/50 hover:bg-slate-850 hover:text-indigo-400 transition-colors border border-slate-700/50"
                    title="Go to Dashboard"
                  >
                    <Activity className="w-4 h-4" />
                  </Link>

                  <button
                    onClick={handleLogout}
                    className="flex items-center gap-1 px-3 py-1.5 rounded-md text-xs font-semibold text-rose-400 bg-rose-950/20 hover:bg-rose-900/30 border border-rose-900/40 transition-colors"
                  >
                    <LogOut className="w-3.5 h-3.5" />
                    Logout
                  </button>
                </div>
              ) : (
                <div className="flex items-center gap-2">
                  <Link
                    href="/login"
                    className="px-3.5 py-1.5 rounded-md text-sm font-medium text-slate-300 hover:text-white hover:bg-slate-800/40 transition-colors"
                  >
                    Sign In
                  </Link>
                  <Link
                    href="/register"
                    className="btn-cyber-primary px-3.5 py-1.5 rounded-md text-sm font-semibold text-white tracking-wide"
                  >
                    Enroll Now
                  </Link>
                </div>
              )}
            </div>
          </div>
        </div>
      </header>

      {/* Main Content Area */}
      <main className="flex-grow flex flex-col">{children}</main>

      {/* Footer */}
      <footer className="border-t border-slate-900 bg-slate-950/80 py-6 mt-auto">
        <div className="max-w-7xl mx-auto px-4 sm:px-6 lg:px-8 flex flex-col md:flex-row items-center justify-between gap-4">
          <div className="flex items-center gap-2 text-slate-500 text-xs">
            <Shield className="w-4 h-4 text-slate-600" />
            <span>&copy; {new Date().getFullYear()} Key Dynamics biometrics security lab. For demonstration purposes only.</span>
          </div>

          <div className="flex items-center gap-6">
            <div className="flex items-center gap-1.5 text-emerald-500 text-xs font-semibold bg-emerald-950/20 px-2.5 py-1 rounded-full border border-emerald-900/30">
              <span className="w-1.5 h-1.5 rounded-full bg-emerald-500 animate-pulse" />
              <span>JWT & HTTPS Active</span>
            </div>

            <div className="flex items-center gap-1.5 text-cyan-500 text-xs font-semibold bg-cyan-950/20 px-2.5 py-1 rounded-full border border-cyan-900/30">
              <Cpu className="w-3.5 h-3.5" />
              <span>AI Core: scikit-learn Ready</span>
            </div>
          </div>
        </div>
      </footer>
    </div>
  );
}
