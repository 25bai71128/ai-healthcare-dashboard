import { subDays } from "date-fns";
import { prisma } from "@/lib/db";
import { requireUserId } from "@/lib/api/auth";
import { handleApiError, ok } from "@/lib/api/http";
import { getPrimaryPatient, resolvePatientId } from "@/lib/patients/access";
import { buildTimeline } from "@/lib/patients/timeline";

export async function GET(request: Request) {
  try {
    const userId = await requireUserId();
    const { searchParams } = new URL(request.url);
    const requestedPatientId = searchParams.get("patientId");

    const patientId = requestedPatientId
      ? await resolvePatientId(userId, requestedPatientId)
      : (await getPrimaryPatient(userId)).id;

    const [appointments, medicationLogs, labResults] = await Promise.all([
      prisma.appointment.findMany({
        where: {
          patientId,
          startsAt: { gte: subDays(new Date(), 120) },
        },
        orderBy: { startsAt: "desc" },
        take: 100,
      }),
      prisma.medicationLog.findMany({
        where: {
          patientId,
          scheduledFor: { gte: subDays(new Date(), 120) },
        },
        orderBy: { scheduledFor: "desc" },
        take: 100,
      }),
      prisma.labResult.findMany({
        where: {
          patientId,
          takenAt: { gte: subDays(new Date(), 180) },
        },
        orderBy: { takenAt: "desc" },
        take: 100,
      }),
    ]);

    return ok({
      events: buildTimeline({ appointments, medicationLogs, labResults }),
    });
  } catch (error) {
    return handleApiError(error);
  }
}
