import { prisma } from "@/lib/db";
import { requireUserId } from "@/lib/api/auth";
import { ApiError, handleApiError, ok } from "@/lib/api/http";
import { parseJsonBody } from "@/lib/api/parse";
import { resolvePatientId } from "@/lib/patients/access";
import { serializeAppointment } from "@/lib/patients/serializers";
import { encryptField } from "@/lib/security/encryption";
import { appointmentPatchSchema } from "@/lib/validation/schemas";

async function loadOwnedAppointment(id: string, userId: string) {
  const record = await prisma.appointment.findFirst({
    where: {
      id,
      patient: {
        ownerId: userId,
      },
    },
  });

  if (!record) {
    throw new ApiError(404, "NOT_FOUND", "Appointment was not found.");
  }

  return record;
}

export async function GET(_: Request, { params }: { params: Promise<{ id: string }> }) {
  try {
    const userId = await requireUserId();
    const { id } = await params;

    const record = await loadOwnedAppointment(id, userId);
    return ok({ appointment: serializeAppointment(record) });
  } catch (error) {
    return handleApiError(error);
  }
}

export async function PATCH(request: Request, { params }: { params: Promise<{ id: string }> }) {
  try {
    const userId = await requireUserId();
    const { id } = await params;
    await loadOwnedAppointment(id, userId);

    const body = await parseJsonBody(request, appointmentPatchSchema);
    const patientId = body.patientId ? await resolvePatientId(userId, body.patientId) : undefined;

    const updated = await prisma.appointment.update({
      where: { id },
      data: {
        patientId,
        startsAt: body.startsAt,
        endsAt: body.endsAt,
        provider: body.provider,
        reason: body.reason,
        status: body.status,
        notes: body.notes === undefined ? undefined : encryptField(body.notes),
      },
    });

    return ok({ appointment: serializeAppointment(updated) });
  } catch (error) {
    return handleApiError(error);
  }
}

export async function DELETE(_: Request, { params }: { params: Promise<{ id: string }> }) {
  try {
    const userId = await requireUserId();
    const { id } = await params;
    await loadOwnedAppointment(id, userId);

    await prisma.appointment.delete({ where: { id } });
    return ok({ deleted: true });
  } catch (error) {
    return handleApiError(error);
  }
}
