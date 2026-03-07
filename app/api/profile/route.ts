import { prisma } from "@/lib/db";
import { requireUserId } from "@/lib/api/auth";
import { handleApiError, ok } from "@/lib/api/http";
import { getPrimaryPatient, resolvePatientId } from "@/lib/patients/access";
import { serializePatient } from "@/lib/patients/serializers";
import { CLINICAL_DECISION_DISCLAIMER, PHI_DISCLAIMER } from "@/lib/security/compliance";

export async function GET(request: Request) {
  try {
    const userId = await requireUserId();
    const { searchParams } = new URL(request.url);
    const requestedPatientId = searchParams.get("patientId");

    const patientId = requestedPatientId
      ? await resolvePatientId(userId, requestedPatientId)
      : (await getPrimaryPatient(userId)).id;

    const patient = await prisma.patient.findUniqueOrThrow({
      where: { id: patientId },
    });

    const [appointmentsCount, medicationsCount, vitalsCount] = await Promise.all([
      prisma.appointment.count({ where: { patientId } }),
      prisma.medication.count({ where: { patientId } }),
      prisma.vital.count({ where: { patientId } }),
    ]);

    return ok({
      patient: serializePatient(patient),
      stats: {
        appointmentsCount,
        medicationsCount,
        vitalsCount,
      },
      disclaimers: [PHI_DISCLAIMER, CLINICAL_DECISION_DISCLAIMER],
    });
  } catch (error) {
    return handleApiError(error);
  }
}
