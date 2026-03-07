import type { Appointment, Medication, Vital } from "@prisma/client";
import { describe, expect, it } from "vitest";
import { buildCriticalAlerts } from "@/lib/patients/alerts";

function asAppointment(partial: Partial<Appointment>): Appointment {
  return {
    id: "a1",
    patientId: "p1",
    startsAt: new Date(),
    endsAt: null,
    provider: "Dr. Test",
    reason: "Follow-up",
    status: "SCHEDULED",
    notes: null,
    createdAt: new Date(),
    updatedAt: new Date(),
    ...partial,
  } as Appointment;
}

function asMedication(partial: Partial<Medication>): Medication {
  return {
    id: "m1",
    patientId: "p1",
    name: "TestMed",
    dosage: "10mg",
    schedule: "Daily",
    nextDoseAt: new Date(),
    lastTakenAt: null,
    adherencePct: 90,
    status: "ACTIVE",
    instructions: null,
    createdAt: new Date(),
    updatedAt: new Date(),
    ...partial,
  } as Medication;
}

function asVital(partial: Partial<Vital>): Vital {
  return {
    id: "v1",
    patientId: "p1",
    measuredAt: new Date(),
    heartRate: 90,
    systolic: 120,
    diastolic: 80,
    glucose: 120,
    oxygenSat: 98,
    temperature: 36.7,
    source: "test",
    createdAt: new Date(),
    ...partial,
  } as Vital;
}

describe("buildCriticalAlerts", () => {
  it("returns critical alert for severely abnormal vitals", () => {
    const now = new Date("2026-03-07T12:00:00.000Z");

    const alerts = buildCriticalAlerts({
      now,
      appointments: [],
      medications: [],
      vitals: [asVital({ heartRate: 140 })],
    });

    expect(alerts).toHaveLength(1);
    expect(alerts[0].severity).toBe("critical");
    expect(alerts[0].type).toBe("ABNORMAL_VITAL");
  });

  it("returns upcoming and overdue alerts", () => {
    const now = new Date("2026-03-07T12:00:00.000Z");

    const alerts = buildCriticalAlerts({
      now,
      appointments: [asAppointment({ startsAt: new Date("2026-03-07T16:00:00.000Z") })],
      medications: [asMedication({ nextDoseAt: new Date("2026-03-07T07:00:00.000Z") })],
      vitals: [],
    });

    expect(alerts.some((alert) => alert.type === "UPCOMING_APPOINTMENT")).toBe(true);
    expect(alerts.some((alert) => alert.type === "OVERDUE_MEDICATION")).toBe(true);
  });
});
