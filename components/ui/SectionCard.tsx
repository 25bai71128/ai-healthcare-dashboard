import { cn } from "@/lib/utils";

export function SectionCard({
  className,
  children,
}: {
  className?: string;
  children: React.ReactNode;
}) {
  return <section className={cn("panel p-4 sm:p-5", className)}>{children}</section>;
}
