import { prisma } from "@/lib/db";
import { requireUserId } from "@/lib/api/auth";
import { handleApiError, ok } from "@/lib/api/http";
import { parseJsonBody } from "@/lib/api/parse";
import { getPrimaryPatient, resolvePatientId } from "@/lib/patients/access";
import { serializeMedication } from "@/lib/patients/serializers";
import { encryptField } from "@/lib/security/encryption";
import { medicationSchema } from "@/lib/validation/schemas";

export async function GET(request: Request) {
  try {
    const userId = await requireUserId();
    const { searchParams } = new URL(request.url);
    const requestedPatientId = searchParams.get("patientId");

    const patientId = requestedPatientId
      ? await resolvePatientId(userId, requestedPatientId)
      : (await getPrimaryPatient(userId)).id;

    const rows = await prisma.medication.findMany({
      where: { patientId },
      orderBy: { nextDoseAt: "asc" },
      take: 250,
    });

    return ok({ medications: rows.map(serializeMedication) });
  } catch (error) {
    return handleApiError(error);
  }
}

export async function POST(request: Request) {
  try {
    const userId = await requireUserId();
    const body = await parseJsonBody(request, medicationSchema);

    const patientId = body.patientId
      ? await resolvePatientId(userId, body.patientId)
      : (await getPrimaryPatient(userId)).id;

    const created = await prisma.medication.create({
      data: {
        patientId,
        name: body.name,
        dosage: body.dosage,
        schedule: body.schedule,
        nextDoseAt: body.nextDoseAt,
        lastTakenAt: body.lastTakenAt,
        adherencePct: body.adherencePct,
        status: body.status,
        instructions: encryptField(body.instructions),
      },
    });

    return ok({ medication: serializeMedication(created) }, 201);
  } catch (error) {
    return handleApiError(error);
  }
}
