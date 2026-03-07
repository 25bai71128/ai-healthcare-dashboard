"use client";

import { useState } from "react";
import { signIn } from "next-auth/react";
import { useRouter, useSearchParams } from "next/navigation";
import type { Route } from "next";

export function LoginForm() {
  const router = useRouter();
  const searchParams = useSearchParams();
  const [email, setEmail] = useState("");
  const [password, setPassword] = useState("");
  const [submitting, setSubmitting] = useState(false);
  const [error, setError] = useState<string | null>(null);

  const redirectTarget = searchParams.get("redirect") || "/dashboard";

  async function handleSubmit(event: React.FormEvent<HTMLFormElement>) {
    event.preventDefault();
    setError(null);
    setSubmitting(true);

    const response = await signIn("credentials", {
      email,
      password,
      redirect: false,
    });

    setSubmitting(false);

    if (response?.error) {
      setError("Invalid credentials. Please verify email and password.");
      return;
    }

    const safeRedirect = redirectTarget.startsWith("/") ? redirectTarget : "/dashboard";
    router.push(safeRedirect as Route);
    router.refresh();
  }

  return (
    <form onSubmit={handleSubmit} className="panel mx-auto w-full max-w-md space-y-4 p-6" aria-describedby="auth-help">
      <header className="space-y-1">
        <h1 className="text-2xl font-bold text-slate-900">CarePulse Secure Login</h1>
        <p id="auth-help" className="text-sm text-slate-600">
          This dashboard contains protected health information. Authorized access only.
        </p>
      </header>

      <label className="block text-sm font-semibold text-slate-700" htmlFor="email">
        Email
      </label>
      <input
        id="email"
        name="email"
        type="email"
        required
        autoComplete="email"
        value={email}
        onChange={(event) => setEmail(event.target.value)}
        className="w-full rounded-xl border border-slate-300 bg-white px-3 py-2 text-sm shadow-sm"
      />

      <label className="block text-sm font-semibold text-slate-700" htmlFor="password">
        Password
      </label>
      <input
        id="password"
        name="password"
        type="password"
        required
        autoComplete="current-password"
        minLength={8}
        value={password}
        onChange={(event) => setPassword(event.target.value)}
        className="w-full rounded-xl border border-slate-300 bg-white px-3 py-2 text-sm shadow-sm"
      />

      {error ? (
        <p className="rounded-lg border border-red-200 bg-red-50 px-3 py-2 text-sm text-red-700" role="alert" aria-live="polite">
          {error}
        </p>
      ) : null}

      <button
        type="submit"
        disabled={submitting}
        className="w-full rounded-xl bg-blue-700 px-4 py-2.5 text-sm font-semibold text-white transition hover:bg-blue-800 disabled:cursor-not-allowed disabled:opacity-70"
      >
        {submitting ? "Signing in..." : "Sign in"}
      </button>

      <p className="text-xs text-slate-500">Use the seed credentials configured in your `.env` and Prisma seed.</p>
    </form>
  );
}
