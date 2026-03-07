import type { Appointment, LabResult, Medication, Patient, Vital } from "@prisma/client";
import { decryptField } from "@/lib/security/encryption";

export function serializePatient(patient: Patient) {
  return {
    id: patient.id,
    fullName: patient.fullName,
    dateOfBirth: patient.dateOfBirth?.toISOString() ?? null,
    conditionSummary: patient.conditionSummary,
    sensitiveNotes: decryptField(patient.sensitiveNotes),
    createdAt: patient.createdAt.toISOString(),
    updatedAt: patient.updatedAt.toISOString(),
  };
}

export function serializeAppointment(item: Appointment) {
  return {
    ...item,
    startsAt: item.startsAt.toISOString(),
    endsAt: item.endsAt?.toISOString() ?? null,
    createdAt: item.createdAt.toISOString(),
    updatedAt: item.updatedAt.toISOString(),
    notes: decryptField(item.notes),
  };
}

export function serializeMedication(item: Medication) {
  return {
    ...item,
    nextDoseAt: item.nextDoseAt.toISOString(),
    lastTakenAt: item.lastTakenAt?.toISOString() ?? null,
    createdAt: item.createdAt.toISOString(),
    updatedAt: item.updatedAt.toISOString(),
    instructions: decryptField(item.instructions),
  };
}

export function serializeLabResult(item: LabResult) {
  return {
    ...item,
    takenAt: item.takenAt.toISOString(),
    createdAt: item.createdAt.toISOString(),
    notes: decryptField(item.notes),
  };
}

export function serializeVital(item: Vital) {
  return {
    ...item,
    measuredAt: item.measuredAt.toISOString(),
    createdAt: item.createdAt.toISOString(),
  };
}
