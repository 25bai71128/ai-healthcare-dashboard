import { z } from "zod";

const apiEnvelopeSchema = z.object({
  ok: z.boolean(),
  data: z.unknown().optional(),
  error: z
    .object({
      code: z.string(),
      message: z.string(),
      details: z.unknown().optional(),
    })
    .optional(),
});

async function request<T>(url: string, init?: RequestInit): Promise<T> {
  const response = await fetch(url, {
    ...init,
    credentials: "include",
    headers: {
      "Content-Type": "application/json",
      ...(init?.headers || {}),
    },
  });

  const json = await response.json();
  const parsed = apiEnvelopeSchema.safeParse(json);

  if (!parsed.success) {
    throw new Error("Invalid server response format.");
  }

  if (!response.ok || !parsed.data.ok) {
    const message = parsed.data.error?.message || "Request failed";
    throw new Error(message);
  }

  return parsed.data.data as T;
}

export async function getProfile(patientId?: string | null) {
  const query = patientId ? `?patientId=${encodeURIComponent(patientId)}` : "";
  return request<{
    patient: {
      id: string;
      fullName: string;
      dateOfBirth: string | null;
      conditionSummary: string | null;
      sensitiveNotes: string | null;
      createdAt: string;
      updatedAt: string;
    };
    stats: {
      appointmentsCount: number;
      medicationsCount: number;
      vitalsCount: number;
    };
    disclaimers: string[];
  }>(`/api/profile${query}`);
}

export async function getAlerts(patientId?: string | null) {
  const query = patientId ? `?patientId=${encodeURIComponent(patientId)}` : "";
  return request<{
    alerts: Array<{
      id: string;
      type: "UPCOMING_APPOINTMENT" | "OVERDUE_MEDICATION" | "ABNORMAL_VITAL";
      severity: "critical" | "warning";
      title: string;
      description: string;
      timestamp: string;
      icon: "calendar" | "pill" | "heart";
    }>;
    summary: {
      critical: number;
      warning: number;
    };
  }>(`/api/alerts${query}`);
}

export async function getAppointments(patientId?: string | null) {
  const query = patientId ? `?patientId=${encodeURIComponent(patientId)}` : "";
  return request<{
    appointments: Array<{
      id: string;
      patientId: string;
      startsAt: string;
      endsAt: string | null;
      provider: string;
      reason: string;
      status: "SCHEDULED" | "COMPLETED" | "CANCELLED" | "MISSED";
      notes: string | null;
      createdAt: string;
      updatedAt: string;
    }>;
  }>(`/api/appointments${query}`);
}

export async function getMedications(patientId?: string | null) {
  const query = patientId ? `?patientId=${encodeURIComponent(patientId)}` : "";
  return request<{
    medications: Array<{
      id: string;
      patientId: string;
      name: string;
      dosage: string;
      schedule: string;
      nextDoseAt: string;
      lastTakenAt: string | null;
      adherencePct: number;
      status: "ACTIVE" | "PAUSED" | "STOPPED";
      instructions: string | null;
      createdAt: string;
      updatedAt: string;
    }>;
  }>(`/api/medications${query}`);
}

export async function getVitals(patientId?: string | null) {
  const query = patientId ? `?patientId=${encodeURIComponent(patientId)}` : "";
  return request<{
    vitals: Array<{
      id: string;
      patientId: string;
      measuredAt: string;
      heartRate: number | null;
      systolic: number | null;
      diastolic: number | null;
      glucose: number | null;
      oxygenSat: number | null;
      temperature: number | null;
      source: string | null;
      createdAt: string;
    }>;
  }>(`/api/vitals${query}`);
}

export async function getLabs(patientId?: string | null) {
  const query = patientId ? `?patientId=${encodeURIComponent(patientId)}` : "";
  return request<{
    labResults: Array<{
      id: string;
      patientId: string;
      takenAt: string;
      testName: string;
      value: string;
      unit: string | null;
      referenceRange: string | null;
      status: "NORMAL" | "ABNORMAL" | "CRITICAL";
      notes: string | null;
      createdAt: string;
    }>;
  }>(`/api/labs${query}`);
}

export async function getAnalytics(patientId?: string | null) {
  const query = patientId ? `?patientId=${encodeURIComponent(patientId)}` : "";
  return request<{
    trends: Array<{
      measuredAt: string;
      heartRate: number | null;
      systolic: number | null;
      diastolic: number | null;
      glucose: number | null;
    }>;
    summary: {
      averageHeartRate: number | null;
      averageSystolic: number | null;
      averageDiastolic: number | null;
      averageGlucose: number | null;
      readingsCount: number;
    };
  }>(`/api/analytics${query}`);
}

export async function getTimeline(patientId?: string | null) {
  const query = patientId ? `?patientId=${encodeURIComponent(patientId)}` : "";
  return request<{
    events: Array<{
      id: string;
      kind: "appointment" | "medication" | "lab";
      title: string;
      subtitle: string;
      timestamp: string;
      status: "normal" | "warning" | "critical";
    }>;
  }>(`/api/timeline${query}`);
}

export async function createVital(payload: {
  patientId?: string;
  heartRate?: number;
  systolic?: number;
  diastolic?: number;
  glucose?: number;
  oxygenSat?: number;
  temperature?: number;
  source?: string;
}) {
  return request<{ vital: unknown }>("/api/vitals", {
    method: "POST",
    body: JSON.stringify(payload),
  });
}

export async function askAssistant(payload: { patientId?: string; prompt: string }) {
  return request<{
    response: string;
    safe: boolean;
    reasons: string[];
    disclaimer: string | null;
    personalizedContext: {
      patientName: string;
      medicationCount: number;
      latestVitalTimestamp: string | null;
    };
  }>("/api/assistant", {
    method: "POST",
    body: JSON.stringify(payload),
  });
}

export async function getClusterAnalysis(patientId?: string | null) {
  const query = patientId ? `?patientId=${encodeURIComponent(patientId)}` : "";
  return request<{
    clustering: {
      schema_version: number;
      features_used: string[];
      n_samples: number;
      n_clusters: number;
      pca_components: number;
      pca_explained_variance_ratio: number[];
      clusters: number[];
      projection: Array<{ x: number; y: number; cluster: number; anomaly: boolean }>;
      cluster_profiles: Record<string, Record<string, number>>;
      anomalies: Array<{ index: number; features: Record<string, number>; cluster: number }>;
      summary: { cluster_counts: Record<string, number>; anomaly_count: number };
    };
    source: { measuredAtByIndex: string[] };
  }>(`/api/intelligence/cluster${query}`);
}

export async function getTreatmentRecommendation(patientId?: string | null) {
  const query = patientId ? `?patientId=${encodeURIComponent(patientId)}` : "";
  return request<{
    recommendation: {
      recommended_treatment: string;
      expected_outcome_score: number;
      risk_before: number;
      risk_after: number;
      notes: string;
    };
    inputs: { measuredAt: string };
  }>(`/api/intelligence/treatment${query}`);
}
