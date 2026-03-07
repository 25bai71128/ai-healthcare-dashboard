import { prisma } from "@/lib/db";
import { requireUserId } from "@/lib/api/auth";
import { handleApiError, ok } from "@/lib/api/http";
import { parseJsonBody } from "@/lib/api/parse";
import { assistantPromptSchema } from "@/lib/validation/schemas";
import { getPrimaryPatient, resolvePatientId } from "@/lib/patients/access";
import { generateAssistantResponse } from "@/lib/patients/assistant";
import { CLINICAL_DECISION_DISCLAIMER } from "@/lib/security/compliance";

export async function POST(request: Request) {
  try {
    const userId = await requireUserId();
    const body = await parseJsonBody(request, assistantPromptSchema);

    const patientId = body.patientId
      ? await resolvePatientId(userId, body.patientId)
      : (await getPrimaryPatient(userId)).id;

    const [patient, medications, vitals] = await Promise.all([
      prisma.patient.findUniqueOrThrow({ where: { id: patientId } }),
      prisma.medication.findMany({
        where: { patientId },
        orderBy: { createdAt: "desc" },
      }),
      prisma.vital.findMany({
        where: { patientId },
        orderBy: { measuredAt: "desc" },
        take: 25,
      }),
    ]);

    const ai = generateAssistantResponse({
      prompt: body.prompt,
      patient,
      medications,
      vitals,
    });

    return ok({
      response: ai.response,
      safe: ai.safe,
      reasons: ai.reasons,
      disclaimer: ai.disclaimer ?? CLINICAL_DECISION_DISCLAIMER,
      personalizedContext: {
        patientName: patient.fullName,
        medicationCount: medications.length,
        latestVitalTimestamp: vitals[0]?.measuredAt.toISOString() ?? null,
      },
    });
  } catch (error) {
    return handleApiError(error);
  }
}
