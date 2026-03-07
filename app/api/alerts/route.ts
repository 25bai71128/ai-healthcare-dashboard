import { addHours, subHours } from "date-fns";
import { prisma } from "@/lib/db";
import { requireUserId } from "@/lib/api/auth";
import { handleApiError, ok } from "@/lib/api/http";
import { getPrimaryPatient, resolvePatientId } from "@/lib/patients/access";
import { buildCriticalAlerts } from "@/lib/patients/alerts";

export async function GET(request: Request) {
  try {
    const userId = await requireUserId();
    const { searchParams } = new URL(request.url);
    const requestedPatientId = searchParams.get("patientId");
    const patientId = requestedPatientId
      ? await resolvePatientId(userId, requestedPatientId)
      : (await getPrimaryPatient(userId)).id;

    const now = new Date();

    const [appointments, medications, vitals] = await Promise.all([
      prisma.appointment.findMany({
        where: {
          patientId,
          startsAt: {
            gte: subHours(now, 1),
            lte: addHours(now, 24),
          },
        },
        orderBy: { startsAt: "asc" },
      }),
      prisma.medication.findMany({
        where: {
          patientId,
          status: "ACTIVE",
        },
        orderBy: { nextDoseAt: "asc" },
      }),
      prisma.vital.findMany({
        where: { patientId },
        orderBy: { measuredAt: "desc" },
        take: 24,
      }),
    ]);

    const alerts = buildCriticalAlerts({ now, appointments, medications, vitals });

    return ok({
      alerts,
      summary: {
        critical: alerts.filter((item) => item.severity === "critical").length,
        warning: alerts.filter((item) => item.severity === "warning").length,
      },
    });
  } catch (error) {
    return handleApiError(error);
  }
}
