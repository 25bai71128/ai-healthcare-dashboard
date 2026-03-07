"use client";

import { Line, LineChart, CartesianGrid, ResponsiveContainer, Tooltip, XAxis, YAxis, Legend } from "recharts";
import { SectionCard } from "@/components/ui/SectionCard";

interface TrendPoint {
  measuredAt: string;
  heartRate: number | null;
  systolic: number | null;
  diastolic: number | null;
  glucose: number | null;
}

interface Summary {
  averageHeartRate: number | null;
  averageSystolic: number | null;
  averageDiastolic: number | null;
  averageGlucose: number | null;
  readingsCount: number;
}

function formatAxisDate(value: string) {
  return new Date(value).toLocaleDateString(undefined, { month: "short", day: "numeric" });
}

export function HealthAnalyticsSection({ trends, summary }: { trends: TrendPoint[]; summary: Summary }) {
  return (
    <SectionCard className="space-y-5" aria-label="Health analytics">
      <div>
        <h2 className="text-lg font-bold text-slate-900">Health Analytics</h2>
        <p className="text-sm text-slate-600">Trend view for heart rate, blood pressure, and glucose over time.</p>
      </div>

      <div className="grid gap-3 sm:grid-cols-2 lg:grid-cols-4" aria-label="Vital summary cards">
        <div className="rounded-xl border border-slate-200 bg-slate-50 p-3">
          <p className="text-xs font-semibold uppercase tracking-wide text-slate-500">Avg Heart Rate</p>
          <p className="text-xl font-bold text-slate-900">{summary.averageHeartRate ?? "--"}</p>
        </div>
        <div className="rounded-xl border border-slate-200 bg-slate-50 p-3">
          <p className="text-xs font-semibold uppercase tracking-wide text-slate-500">Avg Systolic</p>
          <p className="text-xl font-bold text-slate-900">{summary.averageSystolic ?? "--"}</p>
        </div>
        <div className="rounded-xl border border-slate-200 bg-slate-50 p-3">
          <p className="text-xs font-semibold uppercase tracking-wide text-slate-500">Avg Diastolic</p>
          <p className="text-xl font-bold text-slate-900">{summary.averageDiastolic ?? "--"}</p>
        </div>
        <div className="rounded-xl border border-slate-200 bg-slate-50 p-3">
          <p className="text-xs font-semibold uppercase tracking-wide text-slate-500">Avg Glucose</p>
          <p className="text-xl font-bold text-slate-900">{summary.averageGlucose ?? "--"}</p>
        </div>
      </div>

      <div className="h-[320px] w-full rounded-xl border border-slate-200 bg-white p-2" role="img" aria-label="Vitals trend chart">
        <ResponsiveContainer width="100%" height="100%">
          <LineChart data={trends} margin={{ top: 12, right: 18, left: 0, bottom: 8 }}>
            <CartesianGrid strokeDasharray="3 3" stroke="#cbd5e1" />
            <XAxis dataKey="measuredAt" tickFormatter={formatAxisDate} minTickGap={20} />
            <YAxis />
            <Tooltip
              labelFormatter={(value) => new Date(String(value)).toLocaleString()}
              formatter={(value: number, name: string) => [value, name]}
            />
            <Legend />
            <Line type="monotone" dataKey="heartRate" stroke="#0f6bff" strokeWidth={2} dot={false} name="Heart Rate" />
            <Line type="monotone" dataKey="systolic" stroke="#d97706" strokeWidth={2} dot={false} name="Systolic" />
            <Line type="monotone" dataKey="diastolic" stroke="#7c3aed" strokeWidth={2} dot={false} name="Diastolic" />
            <Line type="monotone" dataKey="glucose" stroke="#059669" strokeWidth={2} dot={false} name="Glucose" />
          </LineChart>
        </ResponsiveContainer>
      </div>
    </SectionCard>
  );
}
