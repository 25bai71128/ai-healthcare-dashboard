"use client";

export default function GlobalError({
  error,
  reset,
}: {
  error: Error & { digest?: string };
  reset: () => void;
}) {
  return (
    <html lang="en">
      <body className="p-6">
        <main className="mx-auto max-w-xl rounded-2xl border border-red-200 bg-red-50 p-6">
          <h1 className="mb-2 text-xl font-bold text-red-900">Dashboard Error</h1>
          <p className="mb-4 text-sm text-red-800">{error.message}</p>
          <button
            type="button"
            onClick={() => reset()}
            className="rounded-lg bg-red-700 px-3 py-2 text-sm font-semibold text-white hover:bg-red-800"
          >
            Retry
          </button>
        </main>
      </body>
    </html>
  );
}
