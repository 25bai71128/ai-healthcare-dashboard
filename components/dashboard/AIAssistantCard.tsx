"use client";

import { useState } from "react";
import { Bot, ShieldAlert } from "lucide-react";
import { SectionCard } from "@/components/ui/SectionCard";
import { useAssistant } from "@/lib/hooks/useDashboardData";

export function AIAssistantCard({ patientId }: { patientId?: string }) {
  const [prompt, setPrompt] = useState("");
  const assistant = useAssistant();

  async function submitPrompt(event: React.FormEvent<HTMLFormElement>) {
    event.preventDefault();
    if (!prompt.trim()) return;

    await assistant.mutateAsync({
      patientId,
      prompt,
    });
  }

  return (
    <SectionCard className="space-y-4" aria-label="AI assistant">
      <header className="space-y-1">
        <h2 className="inline-flex items-center gap-2 text-lg font-bold text-slate-900">
          <Bot className="h-5 w-5" aria-hidden />
          AI Assistant
        </h2>
        <p className="text-sm text-slate-600">Context-aware responses are generated from the latest profile, medication, and vitals data.</p>
      </header>

      <form className="space-y-3" onSubmit={submitPrompt}>
        <label htmlFor="assistantPrompt" className="text-sm font-semibold text-slate-700">
          Ask a patient-specific clinical question
        </label>
        <textarea
          id="assistantPrompt"
          value={prompt}
          onChange={(event) => setPrompt(event.target.value)}
          rows={4}
          className="w-full rounded-xl border border-slate-300 bg-white px-3 py-2 text-sm"
          placeholder="Example: How should I prepare for this patient’s blood pressure follow-up?"
          required
        />
        <button
          type="submit"
          disabled={assistant.isPending}
          className="rounded-xl bg-blue-700 px-4 py-2 text-sm font-semibold text-white hover:bg-blue-800 disabled:cursor-not-allowed disabled:opacity-70"
        >
          {assistant.isPending ? "Analyzing..." : "Generate Answer"}
        </button>
      </form>

      {assistant.error ? (
        <p className="rounded-xl border border-red-200 bg-red-50 px-3 py-2 text-sm text-red-700" role="alert">
          {(assistant.error as Error).message}
        </p>
      ) : null}

      {assistant.data ? (
        <div className="space-y-3 rounded-xl border border-slate-200 bg-slate-50 p-3" aria-live="polite">
          {assistant.data.disclaimer ? (
            <div className="inline-flex items-start gap-2 rounded-xl border border-amber-300 bg-amber-50 px-3 py-2 text-sm text-amber-900">
              <ShieldAlert className="mt-0.5 h-4 w-4" aria-hidden />
              <span>{assistant.data.disclaimer}</span>
            </div>
          ) : null}
          <p className="text-sm leading-6 text-slate-800">{assistant.data.response}</p>
          <p className="text-xs text-slate-600">
            Context: {assistant.data.personalizedContext.patientName}, {assistant.data.personalizedContext.medicationCount} medications tracked.
          </p>
        </div>
      ) : null}
    </SectionCard>
  );
}
