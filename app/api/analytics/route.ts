import { subDays } from "date-fns";
import { prisma } from "@/lib/db";
import { requireUserId } from "@/lib/api/auth";
import { handleApiError, ok } from "@/lib/api/http";
import { getPrimaryPatient, resolvePatientId } from "@/lib/patients/access";
import { buildVitalTrends, summarizeVitals } from "@/lib/patients/analytics";

export async function GET(request: Request) {
  try {
    const userId = await requireUserId();
    const { searchParams } = new URL(request.url);
    const requestedPatientId = searchParams.get("patientId");

    const patientId = requestedPatientId
      ? await resolvePatientId(userId, requestedPatientId)
      : (await getPrimaryPatient(userId)).id;

    const fromDate = subDays(new Date(), 90);

    const vitals = await prisma.vital.findMany({
      where: {
        patientId,
        measuredAt: {
          gte: fromDate,
        },
      },
      orderBy: { measuredAt: "asc" },
      take: 500,
    });

    return ok({
      trends: buildVitalTrends(vitals),
      summary: summarizeVitals(vitals),
    });
  } catch (error) {
    return handleApiError(error);
  }
}
