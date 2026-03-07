import { StatusBadge } from "@/components/ui/StatusBadge";
import { SectionCard } from "@/components/ui/SectionCard";
import { toLocalDateTime } from "@/lib/utils";

interface TimelineEvent {
  id: string;
  kind: "appointment" | "medication" | "lab";
  title: string;
  subtitle: string;
  timestamp: string;
  status: "normal" | "warning" | "critical";
}

const kindLabel: Record<TimelineEvent["kind"], string> = {
  appointment: "Appointment",
  medication: "Medication",
  lab: "Lab",
};

export function TimelineSection({ events }: { events: TimelineEvent[] }) {
  return (
    <SectionCard className="space-y-4" aria-label="Clinical timeline">
      <div>
        <h2 className="text-lg font-bold text-slate-900">Clinical Timeline</h2>
        <p className="text-sm text-slate-600">Appointments, medication adherence, and lab result milestones.</p>
      </div>

      {events.length === 0 ? (
        <p className="text-sm text-slate-600">No timeline events are available yet.</p>
      ) : (
        <ul className="space-y-3" role="list">
          {events.slice(0, 20).map((event) => (
            <li key={event.id} className="rounded-xl border border-slate-200 bg-white p-3">
              <div className="mb-1 flex items-start justify-between gap-2">
                <p className="text-sm font-semibold text-slate-900">{event.title}</p>
                <StatusBadge tone={event.status}>{kindLabel[event.kind]}</StatusBadge>
              </div>
              <p className="text-sm text-slate-700">{event.subtitle}</p>
              <p className="mt-1 text-xs font-medium text-slate-500">{toLocalDateTime(event.timestamp)}</p>
            </li>
          ))}
        </ul>
      )}
    </SectionCard>
  );
}
