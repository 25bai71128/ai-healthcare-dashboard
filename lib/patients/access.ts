import { prisma } from "@/lib/db";
import { ApiError } from "@/lib/api/http";

export async function getPrimaryPatient(userId: string) {
  const patient = await prisma.patient.findFirst({
    where: { ownerId: userId },
    orderBy: { createdAt: "asc" },
  });

  if (!patient) {
    throw new ApiError(404, "PATIENT_NOT_FOUND", "No patient profile found for the authenticated user.");
  }

  return patient;
}

export async function resolvePatientId(userId: string, requestedPatientId?: string | null) {
  if (!requestedPatientId) {
    const primary = await getPrimaryPatient(userId);
    return primary.id;
  }

  const patient = await prisma.patient.findFirst({
    where: {
      id: requestedPatientId,
      ownerId: userId,
    },
    select: { id: true },
  });

  if (!patient) {
    throw new ApiError(403, "FORBIDDEN", "You do not have permission to access this patient record.");
  }

  return patient.id;
}
