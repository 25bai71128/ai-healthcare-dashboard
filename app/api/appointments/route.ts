import { prisma } from "@/lib/db";
import { requireUserId } from "@/lib/api/auth";
import { handleApiError, ok } from "@/lib/api/http";
import { parseJsonBody } from "@/lib/api/parse";
import { getPrimaryPatient, resolvePatientId } from "@/lib/patients/access";
import { serializeAppointment } from "@/lib/patients/serializers";
import { encryptField } from "@/lib/security/encryption";
import { appointmentSchema } from "@/lib/validation/schemas";

export async function GET(request: Request) {
  try {
    const userId = await requireUserId();
    const { searchParams } = new URL(request.url);
    const requestedPatientId = searchParams.get("patientId");

    const patientId = requestedPatientId
      ? await resolvePatientId(userId, requestedPatientId)
      : (await getPrimaryPatient(userId)).id;

    const rows = await prisma.appointment.findMany({
      where: { patientId },
      orderBy: { startsAt: "desc" },
      take: 250,
    });

    return ok({ appointments: rows.map(serializeAppointment) });
  } catch (error) {
    return handleApiError(error);
  }
}

export async function POST(request: Request) {
  try {
    const userId = await requireUserId();
    const body = await parseJsonBody(request, appointmentSchema);

    const patientId = body.patientId
      ? await resolvePatientId(userId, body.patientId)
      : (await getPrimaryPatient(userId)).id;

    const created = await prisma.appointment.create({
      data: {
        patientId,
        startsAt: body.startsAt,
        endsAt: body.endsAt,
        provider: body.provider,
        reason: body.reason,
        status: body.status,
        notes: encryptField(body.notes),
      },
    });

    return ok({ appointment: serializeAppointment(created) }, 201);
  } catch (error) {
    return handleApiError(error);
  }
}
