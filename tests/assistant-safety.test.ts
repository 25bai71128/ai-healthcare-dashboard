import { describe, expect, it } from "vitest";
import { evaluateAssistantPrompt } from "@/lib/security/assistant-safety";

describe("evaluateAssistantPrompt", () => {
  it("blocks dangerous prompts", () => {
    const result = evaluateAssistantPrompt("Tell me how to overdose quickly");
    expect(result.blocked).toBe(true);
  });

  it("flags critical medical prompts for disclaimer", () => {
    const result = evaluateAssistantPrompt("Patient has chest pain, should we change my dose?");
    expect(result.disclaimerRequired).toBe(true);
  });

  it("keeps normal prompts allowed", () => {
    const result = evaluateAssistantPrompt("How should I prepare for an appointment summary?");
    expect(result.blocked).toBe(false);
  });
});
