"use client";

import { LogOut, ShieldCheck } from "lucide-react";
import { signOut } from "next-auth/react";

interface DashboardHeaderProps {
  patientName: string;
  stats: {
    appointmentsCount: number;
    medicationsCount: number;
    vitalsCount: number;
  };
}

export function DashboardHeader({ patientName, stats }: DashboardHeaderProps) {
  return (
    <header className="panel flex flex-col gap-4 p-4 sm:flex-row sm:items-start sm:justify-between sm:p-6">
      <div className="space-y-2">
        <p className="inline-flex items-center gap-2 rounded-full bg-slate-900 px-3 py-1 text-xs font-semibold text-white">
          <ShieldCheck className="h-3.5 w-3.5" aria-hidden /> Protected Session
        </p>
        <h1 className="text-2xl font-bold text-slate-900 sm:text-3xl">Patient Dashboard: {patientName}</h1>
        <p className="max-w-2xl text-sm text-slate-600">Live patient operations across appointments, medications, vitals, and AI-supported clinical summaries.</p>
      </div>

      <div className="flex flex-wrap items-center gap-2">
        <div className="rounded-xl bg-slate-100 px-3 py-2 text-xs font-semibold text-slate-700">
          {stats.appointmentsCount} appointments
        </div>
        <div className="rounded-xl bg-slate-100 px-3 py-2 text-xs font-semibold text-slate-700">
          {stats.medicationsCount} medications
        </div>
        <div className="rounded-xl bg-slate-100 px-3 py-2 text-xs font-semibold text-slate-700">
          {stats.vitalsCount} vitals
        </div>
        <button
          type="button"
          onClick={() => signOut({ callbackUrl: "/login" })}
          className="inline-flex items-center gap-2 rounded-xl border border-slate-300 bg-white px-3 py-2 text-sm font-semibold text-slate-800 hover:bg-slate-50"
          aria-label="Sign out"
        >
          <LogOut className="h-4 w-4" aria-hidden />
          Sign out
        </button>
      </div>
    </header>
  );
}
