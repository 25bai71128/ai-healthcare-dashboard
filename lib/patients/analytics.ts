import type { Vital } from "@prisma/client";
import type { VitalTrendPoint } from "@/lib/types";

export function buildVitalTrends(vitals: Vital[]): VitalTrendPoint[] {
  return [...vitals]
    .sort((a, b) => a.measuredAt.getTime() - b.measuredAt.getTime())
    .map((item) => ({
      measuredAt: item.measuredAt.toISOString(),
      heartRate: item.heartRate,
      systolic: item.systolic,
      diastolic: item.diastolic,
      glucose: item.glucose,
    }));
}

function average(values: Array<number | null | undefined>) {
  const filtered = values.filter((value): value is number => typeof value === "number");
  if (!filtered.length) return null;
  const total = filtered.reduce((sum, value) => sum + value, 0);
  return Math.round((total / filtered.length) * 10) / 10;
}

export function summarizeVitals(vitals: Vital[]) {
  return {
    averageHeartRate: average(vitals.map((v) => v.heartRate)),
    averageSystolic: average(vitals.map((v) => v.systolic)),
    averageDiastolic: average(vitals.map((v) => v.diastolic)),
    averageGlucose: average(vitals.map((v) => v.glucose)),
    readingsCount: vitals.length,
  };
}
