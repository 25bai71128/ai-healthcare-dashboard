import { cn } from "@/lib/utils";

const classes = {
  critical: "bg-red-100 text-red-800 border-red-300",
  warning: "bg-amber-100 text-amber-800 border-amber-300",
  normal: "bg-emerald-100 text-emerald-800 border-emerald-300",
};

export function StatusBadge({
  tone,
  children,
}: {
  tone: "critical" | "warning" | "normal";
  children: React.ReactNode;
}) {
  return (
    <span className={cn("inline-flex items-center rounded-full border px-2.5 py-1 text-xs font-semibold", classes[tone])}>
      {children}
    </span>
  );
}
