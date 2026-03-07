function Block({ className }: { className: string }) {
  return <div className={`animate-pulse rounded-xl bg-slate-200 ${className}`} />;
}

export function DashboardSkeleton() {
  return (
    <div className="space-y-4" aria-hidden>
      <Block className="h-28 w-full" />
      <Block className="h-44 w-full" />
      <Block className="h-80 w-full" />
      <div className="grid gap-4 lg:grid-cols-2">
        <Block className="h-80 w-full" />
        <Block className="h-80 w-full" />
      </div>
    </div>
  );
}
