import type { Metadata } from "next";
import { Inter } from "next/font/google";
import "./globals.css";
import Link from "next/link";
import ClientLayout from "./client-layout";

const inter = Inter({ subsets: ["latin"] });

export const metadata: Metadata = {
  title: "AI Keystroke Dynamics Authentication System",
  description: "Advanced cybersecurity biometrics authentication using AI-powered typing behavioral analysis",
};

export default function RootLayout({
  children,
}: {
  children: React.ReactNode;
}) {
  return (
    <html lang="en" className="h-full bg-slate-950 text-slate-100">
      <body className={`${inter.className} min-h-screen flex flex-col cyber-grid relative`}>
        {/* Glow backgrounds */}
        <div className="absolute top-0 left-1/4 w-[500px] h-[500px] bg-indigo-900/10 rounded-full blur-[120px] pointer-events-none -z-10" />
        <div className="absolute bottom-0 right-1/4 w-[600px] h-[600px] bg-blue-900/10 rounded-full blur-[130px] pointer-events-none -z-10" />
        
        <ClientLayout>{children}</ClientLayout>
      </body>
    </html>
  );
}
