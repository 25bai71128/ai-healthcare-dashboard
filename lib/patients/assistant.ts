import type { Medication, Patient, Vital } from "@prisma/client";
import { CRITICAL_DISCLAIMER, evaluateAssistantPrompt } from "@/lib/security/assistant-safety";

interface AssistantInput {
  prompt: string;
  patient: Patient;
  medications: Medication[];
  vitals: Vital[];
}

function summarizeLatestVitals(vitals: Vital[]) {
  const latest = [...vitals].sort((a, b) => b.measuredAt.getTime() - a.measuredAt.getTime())[0];
  if (!latest) {
    return "No recent vitals are available.";
  }

  const parts: string[] = [];
  if (latest.heartRate != null) parts.push(`heart rate ${latest.heartRate} bpm`);
  if (latest.systolic != null && latest.diastolic != null) parts.push(`blood pressure ${latest.systolic}/${latest.diastolic}`);
  if (latest.glucose != null) parts.push(`glucose ${latest.glucose} mg/dL`);
  if (latest.oxygenSat != null) parts.push(`SpO2 ${latest.oxygenSat}%`);

  if (!parts.length) {
    return `Latest vitals were logged on ${latest.measuredAt.toISOString()}, but key values are incomplete.`;
  }

  return `Latest vitals (${latest.measuredAt.toISOString()}): ${parts.join(", ")}.`;
}

function summarizeMedicationState(medications: Medication[]) {
  if (!medications.length) {
    return "No active medications were found in this patient profile.";
  }

  const active = medications.filter((item) => item.status === "ACTIVE");
  if (!active.length) {
    return "The patient currently has no active medication orders.";
  }

  const lines = active.slice(0, 4).map((item) => `${item.name} ${item.dosage} (${item.schedule})`);
  return `Active medication context: ${lines.join("; ")}.`;
}

function personalizedAdvice(prompt: string, patient: Patient, medications: Medication[], vitals: Vital[]) {
  const lowerPrompt = prompt.toLowerCase();
  const focus: string[] = [];

  if (lowerPrompt.includes("blood pressure")) {
    focus.push("Review blood pressure trends and compare home readings with clinic targets.");
  }
  if (lowerPrompt.includes("glucose") || lowerPrompt.includes("sugar")) {
    focus.push("Correlate glucose logs with meals, missed doses, and activity windows.");
  }
  if (lowerPrompt.includes("medication") || lowerPrompt.includes("dose")) {
    focus.push("Verify adherence timestamps before discussing medication adjustments with a clinician.");
  }
  if (lowerPrompt.includes("appointment")) {
    focus.push("Confirm upcoming appointments and bring the latest vitals trend summary to the visit.");
  }

  if (!focus.length) {
    focus.push("Use trend-based monitoring and clinician follow-up for any persistent changes in vitals.");
  }

  const patientSummary = `${patient.fullName} has ${medications.length} tracked medications and ${vitals.length} logged vital readings.`;

  return `${patientSummary} ${summarizeLatestVitals(vitals)} ${summarizeMedicationState(medications)} Suggested next steps: ${focus.join(" ")}`;
}

export function generateAssistantResponse(input: AssistantInput) {
  const safety = evaluateAssistantPrompt(input.prompt);

  if (safety.blocked) {
    return {
      safe: false,
      disclaimer: CRITICAL_DISCLAIMER,
      response:
        "I can’t assist with unsafe or harmful instructions. Please contact a licensed clinician or emergency services for immediate support.",
      reasons: safety.reasons,
    };
  }

  const response = personalizedAdvice(input.prompt, input.patient, input.medications, input.vitals);

  return {
    safe: true,
    disclaimer: safety.disclaimerRequired ? CRITICAL_DISCLAIMER : null,
    response,
    reasons: safety.reasons,
  };
}
