import { AlertTriangle } from "lucide-react";

export function ComplianceNotice({ disclaimers }: { disclaimers: string[] }) {
  return (
    <aside className="panel-soft flex flex-col gap-2 p-4" aria-label="Compliance notices">
      <p className="inline-flex items-center gap-2 text-sm font-bold text-slate-900">
        <AlertTriangle className="h-4 w-4" aria-hidden /> Compliance & Clinical Safety
      </p>
      {disclaimers.map((item, index) => (
        <p key={`${item}-${index}`} className="text-sm text-slate-700">
          {item}
        </p>
      ))}
    </aside>
  );
}
