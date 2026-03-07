import { prisma } from "@/lib/db";
import { requireUserId } from "@/lib/api/auth";
import { ApiError, handleApiError, ok } from "@/lib/api/http";
import { parseJsonBody } from "@/lib/api/parse";
import { resolvePatientId } from "@/lib/patients/access";
import { serializeMedication } from "@/lib/patients/serializers";
import { encryptField } from "@/lib/security/encryption";
import { medicationPatchSchema } from "@/lib/validation/schemas";

async function loadOwnedMedication(id: string, userId: string) {
  const record = await prisma.medication.findFirst({
    where: {
      id,
      patient: {
        ownerId: userId,
      },
    },
  });

  if (!record) {
    throw new ApiError(404, "NOT_FOUND", "Medication record was not found.");
  }

  return record;
}

export async function GET(_: Request, { params }: { params: Promise<{ id: string }> }) {
  try {
    const userId = await requireUserId();
    const { id } = await params;

    const record = await loadOwnedMedication(id, userId);
    return ok({ medication: serializeMedication(record) });
  } catch (error) {
    return handleApiError(error);
  }
}

export async function PATCH(request: Request, { params }: { params: Promise<{ id: string }> }) {
  try {
    const userId = await requireUserId();
    const { id } = await params;
    await loadOwnedMedication(id, userId);

    const body = await parseJsonBody(request, medicationPatchSchema);
    const patientId = body.patientId ? await resolvePatientId(userId, body.patientId) : undefined;

    const updated = await prisma.medication.update({
      where: { id },
      data: {
        patientId,
        name: body.name,
        dosage: body.dosage,
        schedule: body.schedule,
        nextDoseAt: body.nextDoseAt,
        lastTakenAt: body.lastTakenAt,
        adherencePct: body.adherencePct,
        status: body.status,
        instructions: body.instructions === undefined ? undefined : encryptField(body.instructions),
      },
    });

    return ok({ medication: serializeMedication(updated) });
  } catch (error) {
    return handleApiError(error);
  }
}

export async function DELETE(_: Request, { params }: { params: Promise<{ id: string }> }) {
  try {
    const userId = await requireUserId();
    const { id } = await params;
    await loadOwnedMedication(id, userId);

    await prisma.medication.delete({ where: { id } });
    return ok({ deleted: true });
  } catch (error) {
    return handleApiError(error);
  }
}
