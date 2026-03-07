import { prisma } from "@/lib/db";
import { requireUserId } from "@/lib/api/auth";
import { ApiError, handleApiError, ok } from "@/lib/api/http";
import { parseJsonBody } from "@/lib/api/parse";
import { resolvePatientId } from "@/lib/patients/access";
import { serializeVital } from "@/lib/patients/serializers";
import { vitalPatchSchema } from "@/lib/validation/schemas";

async function loadOwnedVital(id: string, userId: string) {
  const record = await prisma.vital.findFirst({
    where: {
      id,
      patient: {
        ownerId: userId,
      },
    },
  });

  if (!record) {
    throw new ApiError(404, "NOT_FOUND", "Vital record was not found.");
  }

  return record;
}

export async function GET(_: Request, { params }: { params: Promise<{ id: string }> }) {
  try {
    const userId = await requireUserId();
    const { id } = await params;

    const record = await loadOwnedVital(id, userId);
    return ok({ vital: serializeVital(record) });
  } catch (error) {
    return handleApiError(error);
  }
}

export async function PATCH(request: Request, { params }: { params: Promise<{ id: string }> }) {
  try {
    const userId = await requireUserId();
    const { id } = await params;
    await loadOwnedVital(id, userId);

    const body = await parseJsonBody(request, vitalPatchSchema);
    const patientId = body.patientId ? await resolvePatientId(userId, body.patientId) : undefined;

    const updated = await prisma.vital.update({
      where: { id },
      data: {
        patientId,
        measuredAt: body.measuredAt,
        heartRate: body.heartRate,
        systolic: body.systolic,
        diastolic: body.diastolic,
        glucose: body.glucose,
        oxygenSat: body.oxygenSat,
        temperature: body.temperature,
        source: body.source,
      },
    });

    return ok({ vital: serializeVital(updated) });
  } catch (error) {
    return handleApiError(error);
  }
}

export async function DELETE(_: Request, { params }: { params: Promise<{ id: string }> }) {
  try {
    const userId = await requireUserId();
    const { id } = await params;
    await loadOwnedVital(id, userId);

    await prisma.vital.delete({ where: { id } });
    return ok({ deleted: true });
  } catch (error) {
    return handleApiError(error);
  }
}
