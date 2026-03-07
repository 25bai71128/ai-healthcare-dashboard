import type { Appointment, Medication, Vital } from "@prisma/client";
import { differenceInHours, isAfter } from "date-fns";
import type { CriticalAlert } from "@/lib/types";

function severityScore(level: CriticalAlert["severity"]) {
  return level === "critical" ? 2 : 1;
}

function pushUpcomingAppointments(now: Date, appointments: Appointment[], output: CriticalAlert[]) {
  for (const appointment of appointments) {
    if (appointment.status !== "SCHEDULED") continue;
    if (appointment.startsAt < now) continue;

    const hoursAway = differenceInHours(appointment.startsAt, now);
    if (hoursAway > 24) continue;

    const severity: CriticalAlert["severity"] = hoursAway <= 3 ? "critical" : "warning";

    output.push({
      id: `appt-${appointment.id}`,
      type: "UPCOMING_APPOINTMENT",
      severity,
      title: `Appointment in ${Math.max(hoursAway, 0)}h`,
      description: `${appointment.reason} with ${appointment.provider}`,
      timestamp: appointment.startsAt.toISOString(),
      icon: "calendar",
    });
  }
}

function pushOverdueMedications(now: Date, medications: Medication[], output: CriticalAlert[]) {
  for (const medication of medications) {
    if (medication.status !== "ACTIVE") continue;
    if (isAfter(medication.nextDoseAt, now)) continue;

    const overdueHours = Math.abs(differenceInHours(medication.nextDoseAt, now));
    const severity: CriticalAlert["severity"] = overdueHours >= 12 ? "critical" : "warning";

    output.push({
      id: `med-${medication.id}`,
      type: "OVERDUE_MEDICATION",
      severity,
      title: `${medication.name} dose overdue`,
      description: `${medication.dosage} (${medication.schedule})`,
      timestamp: medication.nextDoseAt.toISOString(),
      icon: "pill",
    });
  }
}

function getAbnormalVital(vital: Vital): { severity: CriticalAlert["severity"]; summary: string } | null {
  const issues: string[] = [];
  let severity: CriticalAlert["severity"] = "warning";

  if (vital.heartRate != null) {
    if (vital.heartRate < 45 || vital.heartRate > 130) {
      severity = "critical";
      issues.push(`heart rate ${vital.heartRate} bpm`);
    } else if (vital.heartRate < 50 || vital.heartRate > 120) {
      issues.push(`heart rate ${vital.heartRate} bpm`);
    }
  }

  if (vital.systolic != null && vital.diastolic != null) {
    if (vital.systolic >= 180 || vital.diastolic >= 120) {
      severity = "critical";
      issues.push(`BP ${vital.systolic}/${vital.diastolic}`);
    } else if (vital.systolic >= 160 || vital.diastolic >= 100) {
      issues.push(`BP ${vital.systolic}/${vital.diastolic}`);
    }
  }

  if (vital.glucose != null) {
    if (vital.glucose <= 55 || vital.glucose >= 300) {
      severity = "critical";
      issues.push(`glucose ${vital.glucose} mg/dL`);
    } else if (vital.glucose <= 70 || vital.glucose >= 250) {
      issues.push(`glucose ${vital.glucose} mg/dL`);
    }
  }

  if (vital.oxygenSat != null) {
    if (vital.oxygenSat < 90) {
      severity = "critical";
      issues.push(`SpO2 ${vital.oxygenSat}%`);
    } else if (vital.oxygenSat < 94) {
      issues.push(`SpO2 ${vital.oxygenSat}%`);
    }
  }

  if (vital.temperature != null) {
    if (vital.temperature >= 39.5 || vital.temperature < 35) {
      severity = "critical";
      issues.push(`temperature ${vital.temperature.toFixed(1)}°C`);
    } else if (vital.temperature >= 38) {
      issues.push(`temperature ${vital.temperature.toFixed(1)}°C`);
    }
  }

  if (!issues.length) return null;

  return {
    severity,
    summary: issues.join(", "),
  };
}

function pushAbnormalVitals(vitals: Vital[], output: CriticalAlert[]) {
  for (const vital of vitals) {
    const finding = getAbnormalVital(vital);
    if (!finding) continue;

    output.push({
      id: `vital-${vital.id}`,
      type: "ABNORMAL_VITAL",
      severity: finding.severity,
      title: finding.severity === "critical" ? "Critical vital reading" : "Abnormal vital reading",
      description: finding.summary,
      timestamp: vital.measuredAt.toISOString(),
      icon: "heart",
    });
  }
}

export function buildCriticalAlerts(input: {
  now?: Date;
  appointments: Appointment[];
  medications: Medication[];
  vitals: Vital[];
}) {
  const now = input.now ?? new Date();
  const alerts: CriticalAlert[] = [];

  pushUpcomingAppointments(now, input.appointments, alerts);
  pushOverdueMedications(now, input.medications, alerts);
  pushAbnormalVitals(input.vitals, alerts);

  return alerts.sort((a, b) => {
    const severityDiff = severityScore(b.severity) - severityScore(a.severity);
    if (severityDiff !== 0) return severityDiff;
    return new Date(b.timestamp).getTime() - new Date(a.timestamp).getTime();
  });
}
