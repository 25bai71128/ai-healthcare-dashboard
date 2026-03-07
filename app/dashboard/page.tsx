import { redirect } from "next/navigation";
import { getServerSession } from "next-auth";
import { DashboardClient } from "@/components/dashboard/DashboardClient";
import { authOptions } from "@/lib/auth";

export default async function DashboardPage() {
  const session = await getServerSession(authOptions);

  if (!session?.user?.id) {
    redirect("/login");
  }

  return (
    <main id="main-content" className="mx-auto w-full max-w-7xl px-4 py-4 sm:px-6 sm:py-6 lg:px-8">
      <DashboardClient />
    </main>
  );
}
