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

function computeAge(dateOfBirth: Date | null) {
  if (!dateOfBirth) {
    return null;
  }
  const now = new Date();
  let age = now.getUTCFullYear() - dateOfBirth.getUTCFullYear();
  const m = now.getUTCMonth() - dateOfBirth.getUTCMonth();
  if (m < 0 || (m === 0 && now.getUTCDate() < dateOfBirth.getUTCDate())) {
    age -= 1;
  }
  return Math.max(0, age);
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

    const patient = await prisma.patient.findUniqueOrThrow({
      where: { id: patientId },
      select: { dateOfBirth: true },
    });

    const latestVital = await prisma.vital.findFirst({
      where: { patientId },
      orderBy: { measuredAt: "desc" },
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

    if (!latestVital) {
      throw new ApiError(404, "NO_VITALS", "No vitals are available to generate a treatment recommendation.");
    }

    const pythonUrl = resolvePythonServiceUrl();
    const recommendation = await postJson(`${pythonUrl}/predict/treatment`, {
      age: computeAge(patient.dateOfBirth),
      heartRate: latestVital.heartRate,
      systolic: latestVital.systolic,
      diastolic: latestVital.diastolic,
      glucose: latestVital.glucose,
      oxygenSat: latestVital.oxygenSat,
      temperature: latestVital.temperature,
    });

    return ok({
      recommendation,
      inputs: {
        measuredAt: latestVital.measuredAt.toISOString(),
      },
    });
  } catch (error) {
    return handleApiError(error);
  }
}

