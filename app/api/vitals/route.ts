import { prisma } from "@/lib/db";
import { requireUserId } from "@/lib/api/auth";
import { handleApiError, ok } from "@/lib/api/http";
import { parseJsonBody } from "@/lib/api/parse";
import { getPrimaryPatient, resolvePatientId } from "@/lib/patients/access";
import { serializeVital } from "@/lib/patients/serializers";
import { vitalSchema } from "@/lib/validation/schemas";

export async function GET(request: Request) {
  try {
    const userId = await requireUserId();
    const { searchParams } = new URL(request.url);
    const requestedPatientId = searchParams.get("patientId");

    const patientId = requestedPatientId
      ? await resolvePatientId(userId, requestedPatientId)
      : (await getPrimaryPatient(userId)).id;

    const rows = await prisma.vital.findMany({
      where: { patientId },
      orderBy: { measuredAt: "desc" },
      take: 500,
    });

    return ok({ vitals: rows.map(serializeVital) });
  } catch (error) {
    return handleApiError(error);
  }
}

export async function POST(request: Request) {
  try {
    const userId = await requireUserId();
    const body = await parseJsonBody(request, vitalSchema);

    const patientId = body.patientId
      ? await resolvePatientId(userId, body.patientId)
      : (await getPrimaryPatient(userId)).id;

    const created = await prisma.vital.create({
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

    return ok({ vital: serializeVital(created) }, 201);
  } catch (error) {
    return handleApiError(error);
  }
}
