import { prisma } from "@/lib/db";
import { requireUserId } from "@/lib/api/auth";
import { ApiError, handleApiError, ok } from "@/lib/api/http";
import { parseJsonBody } from "@/lib/api/parse";
import { resolvePatientId } from "@/lib/patients/access";
import { serializeLabResult } from "@/lib/patients/serializers";
import { encryptField } from "@/lib/security/encryption";
import { labResultPatchSchema } from "@/lib/validation/schemas";

async function loadOwnedLabResult(id: string, userId: string) {
  const record = await prisma.labResult.findFirst({
    where: {
      id,
      patient: {
        ownerId: userId,
      },
    },
  });

  if (!record) {
    throw new ApiError(404, "NOT_FOUND", "Lab result was not found.");
  }

  return record;
}

export async function GET(_: Request, { params }: { params: Promise<{ id: string }> }) {
  try {
    const userId = await requireUserId();
    const { id } = await params;

    const record = await loadOwnedLabResult(id, userId);
    return ok({ labResult: serializeLabResult(record) });
  } catch (error) {
    return handleApiError(error);
  }
}

export async function PATCH(request: Request, { params }: { params: Promise<{ id: string }> }) {
  try {
    const userId = await requireUserId();
    const { id } = await params;
    await loadOwnedLabResult(id, userId);

    const body = await parseJsonBody(request, labResultPatchSchema);
    const patientId = body.patientId ? await resolvePatientId(userId, body.patientId) : undefined;

    const updated = await prisma.labResult.update({
      where: { id },
      data: {
        patientId,
        takenAt: body.takenAt,
        testName: body.testName,
        value: body.value,
        unit: body.unit,
        referenceRange: body.referenceRange,
        status: body.status,
        notes: body.notes === undefined ? undefined : encryptField(body.notes),
      },
    });

    return ok({ labResult: serializeLabResult(updated) });
  } catch (error) {
    return handleApiError(error);
  }
}

export async function DELETE(_: Request, { params }: { params: Promise<{ id: string }> }) {
  try {
    const userId = await requireUserId();
    const { id } = await params;
    await loadOwnedLabResult(id, userId);

    await prisma.labResult.delete({ where: { id } });
    return ok({ deleted: true });
  } catch (error) {
    return handleApiError(error);
  }
}
