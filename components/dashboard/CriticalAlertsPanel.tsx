import { Activity, CalendarClock, Pill } from "lucide-react";
import { toLocalDateTime } from "@/lib/utils";
import { StatusBadge } from "@/components/ui/StatusBadge";

interface Alert {
  id: string;
  type: "UPCOMING_APPOINTMENT" | "OVERDUE_MEDICATION" | "ABNORMAL_VITAL";
  severity: "critical" | "warning";
  title: string;
  description: string;
  timestamp: string;
  icon: "calendar" | "pill" | "heart";
}

const iconMap = {
  calendar: CalendarClock,
  pill: Pill,
  heart: Activity,
};

export function CriticalAlertsPanel({ alerts }: { alerts: Alert[] }) {
  return (
    <section className="panel p-4 sm:p-5" aria-label="Critical alerts">
      <div className="mb-4 flex items-center justify-between gap-3">
        <h2 className="text-lg font-bold text-slate-900">Critical Alerts</h2>
        <span className="rounded-full bg-slate-900 px-2.5 py-1 text-xs font-semibold text-white" aria-label={`${alerts.length} active alerts`}>
          {alerts.length} active
        </span>
      </div>

      {alerts.length === 0 ? (
        <p className="rounded-xl border border-emerald-200 bg-emerald-50 px-3 py-2 text-sm text-emerald-700" role="status">
          No critical or warning alerts right now.
        </p>
      ) : (
        <ul className="grid gap-3 sm:grid-cols-2" role="list">
          {alerts.map((alert) => {
            const Icon = iconMap[alert.icon];
            const tone =
              alert.severity === "critical"
                ? "border-red-300 bg-red-50"
                : "border-amber-300 bg-amber-50";

            return (
              <li key={alert.id} className={`rounded-xl border p-3 ${tone}`}>
                <div className="mb-1 flex items-start justify-between gap-2">
                  <p className="inline-flex items-center gap-2 text-sm font-semibold text-slate-900">
                    <Icon className="h-4 w-4" aria-hidden />
                    {alert.title}
                  </p>
                  <StatusBadge tone={alert.severity}>{alert.severity === "critical" ? "Critical" : "Warning"}</StatusBadge>
                </div>
                <p className="text-sm text-slate-700">{alert.description}</p>
                <p className="mt-2 text-xs font-medium text-slate-600">{toLocalDateTime(alert.timestamp)}</p>
              </li>
            );
          })}
        </ul>
      )}
    </section>
  );
}
