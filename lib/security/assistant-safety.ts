const blockedPatterns = [
  /how\s+to\s+overdose/i,
  /self[-\s]?harm/i,
  /suicide/i,
  /ignore\s+doctor/i,
  /stop\s+all\s+medications/i,
  /double\s+my\s+dose/i,
];

const criticalAdvicePatterns = [
  /chest\s+pain/i,
  /shortness\s+of\s+breath/i,
  /stroke/i,
  /seizure/i,
  /severe\s+bleeding/i,
  /change\s+my\s+dose/i,
  /can\s+i\s+stop\s+my\s+medication/i,
  /emergency/i,
];

export interface SafetyEvaluation {
  blocked: boolean;
  disclaimerRequired: boolean;
  reasons: string[];
}

export function evaluateAssistantPrompt(prompt: string): SafetyEvaluation {
  const reasons: string[] = [];

  const blocked = blockedPatterns.some((pattern) => {
    const match = pattern.test(prompt);
    if (match) reasons.push(`blocked:${pattern.source}`);
    return match;
  });

  const disclaimerRequired = criticalAdvicePatterns.some((pattern) => {
    const match = pattern.test(prompt);
    if (match) reasons.push(`critical:${pattern.source}`);
    return match;
  });

  return {
    blocked,
    disclaimerRequired,
    reasons,
  };
}

export const CRITICAL_DISCLAIMER =
  "This assistant does not replace licensed medical judgment. For urgent symptoms or medication changes, contact your clinician or emergency services immediately.";
