import fs from "node:fs";
import path from "node:path";
import { PrismaClient, AppointmentStatus, MedicationStatus, AdherenceStatus, LabStatus, UserRole } from "@prisma/client";
import { hashPassword } from "../lib/security/password";
import { encryptField } from "../lib/security/encryption";

const prisma = new PrismaClient();

function loadCsvRows() {
  const csvPath = path.join(process.cwd(), "data", "patient_data.csv");
  const raw = fs.readFileSync(csvPath, "utf8").trim();
  const [header, ...lines] = raw.split(/\r?\n/);
  if (!header) return [];

  return lines.map((line) => {
    const [age, bloodPressure, cholesterol, diabetesRisk] = line.split(",").map((token) => token.trim());
    return {
      age: Number(age),
      bloodPressure: Number(bloodPressure),
      cholesterol: Number(cholesterol),
      diabetesRisk: Number(diabetesRisk),
    };
  });
}

async function main() {
  const email = (process.env.SEED_USER_EMAIL || "clinician@carepulse.dev").toLowerCase();
  const password = process.env.SEED_USER_PASSWORD || "ChangeThisNow123!";
  const patientName = process.env.SEED_PATIENT_NAME || "Jordan Smith";

  const user = await prisma.user.upsert({
    where: { email },
    create: {
      email,
      name: "Primary Clinician",
      role: UserRole.ADMIN,
      passwordHash: await hashPassword(password),
    },
    update: {
      passwordHash: await hashPassword(password),
      role: UserRole.ADMIN,
    },
  });

  const existingPatient = await prisma.patient.findFirst({
    where: {
      ownerId: user.id,
      fullName: patientName,
    },
  });

  const patient =
    existingPatient ??
    (await prisma.patient.create({
      data: {
        ownerId: user.id,
        fullName: patientName,
        conditionSummary: "Hypertension and glycemic monitoring",
        sensitiveNotes: encryptField("History of fluctuating blood pressure and intermittent adherence concerns."),
      },
    }));

  await prisma.appointment.deleteMany({ where: { patientId: patient.id } });
  await prisma.medicationLog.deleteMany({ where: { patientId: patient.id } });
  await prisma.medication.deleteMany({ where: { patientId: patient.id } });
  await prisma.vital.deleteMany({ where: { patientId: patient.id } });
  await prisma.labResult.deleteMany({ where: { patientId: patient.id } });

  const now = new Date();

  await prisma.appointment.createMany({
    data: [
      {
        patientId: patient.id,
        startsAt: new Date(now.getTime() + 6 * 60 * 60 * 1000),
        endsAt: new Date(now.getTime() + 7 * 60 * 60 * 1000),
        provider: "Dr. Anita Patel",
        reason: "Hypertension follow-up",
        status: AppointmentStatus.SCHEDULED,
        notes: encryptField("Discuss nighttime blood pressure spikes."),
      },
      {
        patientId: patient.id,
        startsAt: new Date(now.getTime() + 20 * 60 * 60 * 1000),
        provider: "Dr. R. Nguyen",
        reason: "Medication reconciliation",
        status: AppointmentStatus.SCHEDULED,
        notes: encryptField("Review possible ACE inhibitor adjustment."),
      },
      {
        patientId: patient.id,
        startsAt: new Date(now.getTime() - 3 * 24 * 60 * 60 * 1000),
        provider: "Dr. Anita Patel",
        reason: "Routine consultation",
        status: AppointmentStatus.COMPLETED,
      },
    ],
  });

  const meds = await prisma.$transaction([
    prisma.medication.create({
      data: {
        patientId: patient.id,
        name: "Lisinopril",
        dosage: "10mg",
        schedule: "Daily 08:00",
        nextDoseAt: new Date(now.getTime() - 4 * 60 * 60 * 1000),
        lastTakenAt: new Date(now.getTime() - 24 * 60 * 60 * 1000),
        adherencePct: 82,
        status: MedicationStatus.ACTIVE,
        instructions: encryptField("Take with water and track dizziness episodes."),
      },
    }),
    prisma.medication.create({
      data: {
        patientId: patient.id,
        name: "Metformin",
        dosage: "500mg",
        schedule: "Twice daily",
        nextDoseAt: new Date(now.getTime() + 2 * 60 * 60 * 1000),
        lastTakenAt: new Date(now.getTime() - 10 * 60 * 60 * 1000),
        adherencePct: 91,
        status: MedicationStatus.ACTIVE,
        instructions: encryptField("Take with meals to lower GI side effects."),
      },
    }),
  ]);

  const rows = loadCsvRows().slice(0, 60);
  await prisma.vital.createMany({
    data: rows.map((row, index) => {
      const measuredAt = new Date(now.getTime() - (rows.length - index) * 6 * 60 * 60 * 1000);
      const diastolic = Math.max(55, Math.round(row.bloodPressure * 0.62));

      return {
        patientId: patient.id,
        measuredAt,
        heartRate: 58 + (row.age % 18) + row.diabetesRisk * 6,
        systolic: row.bloodPressure,
        diastolic,
        glucose: 85 + Math.round((row.cholesterol - 160) * 0.5),
        oxygenSat: 97 - (row.diabetesRisk ? 2 : 0),
        temperature: 36.5 + (row.diabetesRisk ? 0.3 : 0),
        source: "seeded-csv",
      };
    }),
  });

  await prisma.labResult.createMany({
    data: [
      {
        patientId: patient.id,
        takenAt: new Date(now.getTime() - 6 * 24 * 60 * 60 * 1000),
        testName: "HbA1c",
        value: "7.4",
        unit: "%",
        referenceRange: "<5.7",
        status: LabStatus.ABNORMAL,
        notes: encryptField("Follow-up glycemic plan recommended."),
      },
      {
        patientId: patient.id,
        takenAt: new Date(now.getTime() - 12 * 24 * 60 * 60 * 1000),
        testName: "LDL Cholesterol",
        value: "162",
        unit: "mg/dL",
        referenceRange: "<100",
        status: LabStatus.CRITICAL,
        notes: encryptField("High cardiovascular risk marker."),
      },
    ],
  });

  await prisma.medicationLog.createMany({
    data: [
      {
        medicationId: meds[0].id,
        patientId: patient.id,
        scheduledFor: new Date(now.getTime() - 24 * 60 * 60 * 1000),
        takenAt: new Date(now.getTime() - 23.2 * 60 * 60 * 1000),
        status: AdherenceStatus.TAKEN,
      },
      {
        medicationId: meds[0].id,
        patientId: patient.id,
        scheduledFor: new Date(now.getTime() - 4 * 60 * 60 * 1000),
        status: AdherenceStatus.MISSED,
        note: encryptField("Patient reported travel-related miss."),
      },
      {
        medicationId: meds[1].id,
        patientId: patient.id,
        scheduledFor: new Date(now.getTime() - 10 * 60 * 60 * 1000),
        takenAt: new Date(now.getTime() - 9.7 * 60 * 60 * 1000),
        status: AdherenceStatus.TAKEN,
      },
    ],
  });

  console.log(`Seed complete for ${email}. Patient ID: ${patient.id}`);
}

main()
  .catch((error) => {
    console.error(error);
    process.exit(1);
  })
  .finally(async () => {
    await prisma.$disconnect();
  });
