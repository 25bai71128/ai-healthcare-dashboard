import { z } from "zod";

const isoDateSchema = z
  .string()
  .datetime({ offset: true })
  .or(z.string().datetime())
  .transform((value) => new Date(value));

export const idParamSchema = z.object({
  id: z.string().min(1),
});

export const patientQuerySchema = z.object({
  patientId: z.string().optional(),
});

export const appointmentSchema = z.object({
  patientId: z.string().optional(),
  startsAt: isoDateSchema,
  endsAt: isoDateSchema.optional(),
  provider: z.string().min(2).max(100),
  reason: z.string().min(2).max(300),
  status: z.enum(["SCHEDULED", "COMPLETED", "CANCELLED", "MISSED"]).optional(),
  notes: z.string().max(2000).optional(),
});

export const appointmentPatchSchema = appointmentSchema.partial().extend({
  patientId: z.string().optional(),
});

export const medicationSchema = z.object({
  patientId: z.string().optional(),
  name: z.string().min(2).max(120),
  dosage: z.string().min(1).max(120),
  schedule: z.string().min(2).max(120),
  nextDoseAt: isoDateSchema,
  lastTakenAt: isoDateSchema.optional(),
  adherencePct: z.number().min(0).max(100).optional(),
  status: z.enum(["ACTIVE", "PAUSED", "STOPPED"]).optional(),
  instructions: z.string().max(2000).optional(),
});

export const medicationPatchSchema = medicationSchema.partial().extend({
  patientId: z.string().optional(),
});

export const vitalSchema = z.object({
  patientId: z.string().optional(),
  measuredAt: isoDateSchema.optional(),
  heartRate: z.number().int().min(20).max(240).optional(),
  systolic: z.number().int().min(60).max(260).optional(),
  diastolic: z.number().int().min(30).max(180).optional(),
  glucose: z.number().int().min(20).max(600).optional(),
  oxygenSat: z.number().int().min(40).max(100).optional(),
  temperature: z.number().min(30).max(45).optional(),
  source: z.string().max(80).optional(),
});

export const vitalPatchSchema = vitalSchema.partial().extend({
  patientId: z.string().optional(),
});

export const labResultSchema = z.object({
  patientId: z.string().optional(),
  takenAt: isoDateSchema,
  testName: z.string().min(2).max(140),
  value: z.string().min(1).max(120),
  unit: z.string().max(40).optional(),
  referenceRange: z.string().max(120).optional(),
  status: z.enum(["NORMAL", "ABNORMAL", "CRITICAL"]).optional(),
  notes: z.string().max(2000).optional(),
});

export const labResultPatchSchema = labResultSchema.partial().extend({
  patientId: z.string().optional(),
});

export const assistantPromptSchema = z.object({
  patientId: z.string().optional(),
  prompt: z.string().min(5).max(2000),
});
