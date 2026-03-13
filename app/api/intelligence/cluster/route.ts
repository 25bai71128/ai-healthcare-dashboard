import { prisma } from "@/lib/db";
import { requireUserId } from "@/lib/api/auth";
import { ApiError, handleApiError, ok } from "@/lib/api/http";
import { getPrimaryPatient, resolvePatientId } from "@/lib/patients/access";

function resolvePythonServiceUrl() {
  const url = process.env.AI_PYTHON_SERVICE_URL;
  if (!url) {
    throw new ApiError(
      501,
      "SERVICE_NOT_CONFIGURED",
      "Python AI service is not configured. Set AI_PYTHON_SERVICE_URL (example: http://localhost:8000).",
    );
  }
  return url.replace(/\/$/, "");
}

async function postJson(url: string, payload: unknown) {
  const controller = new AbortController();
  const timeout = setTimeout(() => controller.abort(), 10_000);

  try {
    const response = await fetch(url, {
      method: "POST",
      headers: { "Content-Type": "application/json" },
      body: JSON.stringify(payload),
      signal: controller.signal,
    });

    if (!response.ok) {
      const bodyText = await response.text().catch(() => "");
      throw new ApiError(502, "UPSTREAM_ERROR", "Python AI service returned an error.", {
        status: response.status,
        body: bodyText.slice(0, 2_000),
      });
    }

    return response.json();
  } catch (error) {
    if (error instanceof ApiError) {
      throw error;
    }
    throw new ApiError(502, "UPSTREAM_UNAVAILABLE", "Unable to reach Python AI service.", {
      cause: error instanceof Error ? error.message : String(error),
    });
  } finally {
    clearTimeout(timeout);
  }
}

export async function GET(request: Request) {
  try {
    const userId = await requireUserId();
    const { searchParams } = new URL(request.url);
    const requestedPatientId = searchParams.get("patientId");

    const patientId = requestedPatientId
      ? await resolvePatientId(userId, requestedPatientId)
      : (await getPrimaryPatient(userId)).id;

    const vitals = await prisma.vital.findMany({
      where: { patientId },
      orderBy: { measuredAt: "asc" },
      take: 240,
      select: {
        measuredAt: true,
        heartRate: true,
        systolic: true,
        diastolic: true,
        glucose: true,
        oxygenSat: true,
        temperature: true,
      },
    });

    if (vitals.length === 0) {
      throw new ApiError(404, "NO_VITALS", "No vitals are available to compute clustering and anomaly detection.");
    }

    const records = vitals.map((vital) => ({
      measuredAt: vital.measuredAt.toISOString(),
      heartRate: vital.heartRate,
      systolic: vital.systolic,
      diastolic: vital.diastolic,
      glucose: vital.glucose,
      oxygenSat: vital.oxygenSat,
      temperature: vital.temperature,
    }));

    const pythonUrl = resolvePythonServiceUrl();
    const clustering = await postJson(`${pythonUrl}/predict/cluster`, {
      patients: records,
      features: ["heartRate", "systolic", "diastolic", "glucose", "oxygenSat", "temperature"],
      n_clusters: 3,
      pca_components: 2,
      dbscan_eps: 0.85,
      dbscan_min_samples: 4,
    });

    return ok({
      clustering,
      source: {
        measuredAtByIndex: records.map((row) => row.measuredAt),
      },
    });
  } catch (error) {
    return handleApiError(error);
  }
}
