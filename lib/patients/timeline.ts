import type { Appointment, LabResult, MedicationLog } from "@prisma/client";
import type { DashboardTimelineEvent } from "@/lib/types";

export function buildTimeline(input: {
  appointments: Appointment[];
  medicationLogs: MedicationLog[];
  labResults: LabResult[];
}): DashboardTimelineEvent[] {
  const events: DashboardTimelineEvent[] = [];

  for (const appointment of input.appointments) {
    events.push({
      id: `appt-${appointment.id}`,
      kind: "appointment",
      title: appointment.reason,
      subtitle: `${appointment.provider} • ${appointment.status}`,
      timestamp: appointment.startsAt.toISOString(),
      status: appointment.status === "MISSED" ? "warning" : "normal",
    });
  }

  for (const medEvent of input.medicationLogs) {
    const missed = medEvent.status === "MISSED" || medEvent.status === "SKIPPED";
    events.push({
      id: `med-${medEvent.id}`,
      kind: "medication",
      title: missed ? "Medication dose missed" : "Medication dose taken",
      subtitle: `Scheduled for ${medEvent.scheduledFor.toISOString()}`,
      timestamp: medEvent.takenAt?.toISOString() ?? medEvent.scheduledFor.toISOString(),
      status: missed ? "warning" : "normal",
    });
  }

  for (const lab of input.labResults) {
    events.push({
      id: `lab-${lab.id}`,
      kind: "lab",
      title: `${lab.testName}: ${lab.value}${lab.unit ? ` ${lab.unit}` : ""}`,
      subtitle: lab.referenceRange ? `Range ${lab.referenceRange}` : "Lab result",
      timestamp: lab.takenAt.toISOString(),
      status: lab.status === "CRITICAL" ? "critical" : lab.status === "ABNORMAL" ? "warning" : "normal",
    });
  }

  return events.sort((a, b) => new Date(b.timestamp).getTime() - new Date(a.timestamp).getTime());
}
