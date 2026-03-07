import { StatusBadge } from "@/components/ui/StatusBadge";
import { SectionCard } from "@/components/ui/SectionCard";
import { toLocalDateTime } from "@/lib/utils";

interface Appointment {
  id: string;
  startsAt: string;
  provider: string;
  reason: string;
  status: "SCHEDULED" | "COMPLETED" | "CANCELLED" | "MISSED";
}

interface Medication {
  id: string;
  name: string;
  dosage: string;
  schedule: string;
  adherencePct: number;
  nextDoseAt: string;
  status: "ACTIVE" | "PAUSED" | "STOPPED";
}

interface LabResult {
  id: string;
  takenAt: string;
  testName: string;
  value: string;
  unit: string | null;
  status: "NORMAL" | "ABNORMAL" | "CRITICAL";
}

function toneFromLab(status: LabResult["status"]): "normal" | "warning" | "critical" {
  if (status === "CRITICAL") return "critical";
  if (status === "ABNORMAL") return "warning";
  return "normal";
}

function toneFromAppointment(status: Appointment["status"]): "normal" | "warning" {
  return status === "MISSED" ? "warning" : "normal";
}

export function OperationsSnapshot({
  appointments,
  medications,
  labs,
}: {
  appointments: Appointment[];
  medications: Medication[];
  labs: LabResult[];
}) {
  return (
    <section className="grid gap-4 xl:grid-cols-3" aria-label="Operational summaries">
      <SectionCard className="space-y-3">
        <h2 className="text-base font-bold text-slate-900">Appointments</h2>
        <ul className="space-y-2">
          {appointments.slice(0, 5).map((item) => (
            <li key={item.id} className="rounded-xl border border-slate-200 p-3">
              <div className="mb-1 flex items-center justify-between gap-2">
                <p className="text-sm font-semibold text-slate-900">{item.reason}</p>
                <StatusBadge tone={toneFromAppointment(item.status)}>{item.status}</StatusBadge>
              </div>
              <p className="text-xs text-slate-600">{item.provider}</p>
              <p className="text-xs text-slate-500">{toLocalDateTime(item.startsAt)}</p>
            </li>
          ))}
        </ul>
      </SectionCard>

      <SectionCard className="space-y-3">
        <h2 className="text-base font-bold text-slate-900">Medication Adherence</h2>
        <ul className="space-y-2">
          {medications.slice(0, 5).map((item) => {
            const tone = item.adherencePct < 80 ? "warning" : "normal";
            return (
              <li key={item.id} className="rounded-xl border border-slate-200 p-3">
                <div className="mb-1 flex items-center justify-between gap-2">
                  <p className="text-sm font-semibold text-slate-900">{item.name}</p>
                  <StatusBadge tone={tone}>{Math.round(item.adherencePct)}%</StatusBadge>
                </div>
                <p className="text-xs text-slate-600">
                  {item.dosage} • {item.schedule}
                </p>
                <p className="text-xs text-slate-500">Next dose: {toLocalDateTime(item.nextDoseAt)}</p>
              </li>
            );
          })}
        </ul>
      </SectionCard>

      <SectionCard className="space-y-3">
        <h2 className="text-base font-bold text-slate-900">Recent Labs</h2>
        <ul className="space-y-2">
          {labs.slice(0, 5).map((item) => (
            <li key={item.id} className="rounded-xl border border-slate-200 p-3">
              <div className="mb-1 flex items-center justify-between gap-2">
                <p className="text-sm font-semibold text-slate-900">{item.testName}</p>
                <StatusBadge tone={toneFromLab(item.status)}>{item.status}</StatusBadge>
              </div>
              <p className="text-xs text-slate-600">
                {item.value}
                {item.unit ? ` ${item.unit}` : ""}
              </p>
              <p className="text-xs text-slate-500">{toLocalDateTime(item.takenAt)}</p>
            </li>
          ))}
        </ul>
      </SectionCard>
    </section>
  );
}
