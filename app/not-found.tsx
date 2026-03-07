import Link from "next/link";

export default function NotFoundPage() {
  return (
    <main id="main-content" className="mx-auto flex min-h-screen max-w-xl flex-col items-center justify-center px-4 text-center">
      <h1 className="text-3xl font-bold text-slate-900">Page not found</h1>
      <p className="mt-2 text-sm text-slate-600">The requested page does not exist.</p>
      <Link href="/dashboard" className="mt-4 rounded-xl bg-slate-900 px-4 py-2 text-sm font-semibold text-white">
        Back to dashboard
      </Link>
    </main>
  );
}
