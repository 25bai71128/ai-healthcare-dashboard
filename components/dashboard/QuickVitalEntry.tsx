"use client";

import { useState } from "react";
import { SectionCard } from "@/components/ui/SectionCard";
import { useCreateVital } from "@/lib/hooks/useDashboardData";

export function QuickVitalEntry({ patientId }: { patientId?: string }) {
  const [heartRate, setHeartRate] = useState("");
  const [systolic, setSystolic] = useState("");
  const [diastolic, setDiastolic] = useState("");
  const [glucose, setGlucose] = useState("");

  const createVital = useCreateVital();

  async function submit(event: React.FormEvent<HTMLFormElement>) {
    event.preventDefault();

    await createVital.mutateAsync({
      patientId,
      heartRate: heartRate ? Number(heartRate) : undefined,
      systolic: systolic ? Number(systolic) : undefined,
      diastolic: diastolic ? Number(diastolic) : undefined,
      glucose: glucose ? Number(glucose) : undefined,
      source: "manual-dashboard-entry",
    });

    setHeartRate("");
    setSystolic("");
    setDiastolic("");
    setGlucose("");
  }

  return (
    <SectionCard className="space-y-3" aria-label="Quick vital entry">
      <h2 className="text-lg font-bold text-slate-900">Quick Vital Entry</h2>
      <p className="text-sm text-slate-600">Add a bedside reading. The dashboard updates automatically after save.</p>

      <form onSubmit={submit} className="grid grid-cols-1 gap-3 sm:grid-cols-2">
        <label className="text-sm font-semibold text-slate-700">
          Heart rate (bpm)
          <input
            type="number"
            min={20}
            max={240}
            value={heartRate}
            onChange={(event) => setHeartRate(event.target.value)}
            className="mt-1 w-full rounded-xl border border-slate-300 px-3 py-2 text-sm"
          />
        </label>

        <label className="text-sm font-semibold text-slate-700">
          Glucose (mg/dL)
          <input
            type="number"
            min={20}
            max={600}
            value={glucose}
            onChange={(event) => setGlucose(event.target.value)}
            className="mt-1 w-full rounded-xl border border-slate-300 px-3 py-2 text-sm"
          />
        </label>

        <label className="text-sm font-semibold text-slate-700">
          Systolic
          <input
            type="number"
            min={60}
            max={260}
            value={systolic}
            onChange={(event) => setSystolic(event.target.value)}
            className="mt-1 w-full rounded-xl border border-slate-300 px-3 py-2 text-sm"
          />
        </label>

        <label className="text-sm font-semibold text-slate-700">
          Diastolic
          <input
            type="number"
            min={30}
            max={180}
            value={diastolic}
            onChange={(event) => setDiastolic(event.target.value)}
            className="mt-1 w-full rounded-xl border border-slate-300 px-3 py-2 text-sm"
          />
        </label>

        <div className="sm:col-span-2">
          <button
            type="submit"
            disabled={createVital.isPending}
            className="rounded-xl bg-slate-900 px-4 py-2 text-sm font-semibold text-white hover:bg-slate-800 disabled:cursor-not-allowed disabled:opacity-70"
          >
            {createVital.isPending ? "Saving..." : "Save Vital"}
          </button>
        </div>
      </form>

      {createVital.error ? (
        <p className="rounded-xl border border-red-200 bg-red-50 px-3 py-2 text-sm text-red-700" role="alert">
          {(createVital.error as Error).message}
        </p>
      ) : null}

      {createVital.isSuccess ? (
        <p className="rounded-xl border border-emerald-200 bg-emerald-50 px-3 py-2 text-sm text-emerald-700" role="status">
          Vital saved.
        </p>
      ) : null}
    </SectionCard>
  );
}
