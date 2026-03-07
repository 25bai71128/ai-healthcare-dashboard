import { prisma } from "@/lib/db";
import { requireUserId } from "@/lib/api/auth";
import { handleApiError, ok } from "@/lib/api/http";
import { parseJsonBody } from "@/lib/api/parse";
import { getPrimaryPatient, resolvePatientId } from "@/lib/patients/access";
import { serializeLabResult } from "@/lib/patients/serializers";
import { encryptField } from "@/lib/security/encryption";
import { labResultSchema } from "@/lib/validation/schemas";

export async function GET(request: Request) {
  try {
    const userId = await requireUserId();
    const { searchParams } = new URL(request.url);
    const requestedPatientId = searchParams.get("patientId");

    const patientId = requestedPatientId
      ? await resolvePatientId(userId, requestedPatientId)
      : (await getPrimaryPatient(userId)).id;

    const rows = await prisma.labResult.findMany({
      where: { patientId },
      orderBy: { takenAt: "desc" },
      take: 250,
    });

    return ok({ labResults: rows.map(serializeLabResult) });
  } catch (error) {
    return handleApiError(error);
  }
}

export async function POST(request: Request) {
  try {
    const userId = await requireUserId();
    const body = await parseJsonBody(request, labResultSchema);

    const patientId = body.patientId
      ? await resolvePatientId(userId, body.patientId)
      : (await getPrimaryPatient(userId)).id;

    const created = await prisma.labResult.create({
      data: {
        patientId,
        takenAt: body.takenAt,
        testName: body.testName,
        value: body.value,
        unit: body.unit,
        referenceRange: body.referenceRange,
        status: body.status,
        notes: encryptField(body.notes),
      },
    });

    return ok({ labResult: serializeLabResult(created) }, 201);
  } catch (error) {
    return handleApiError(error);
  }
}
