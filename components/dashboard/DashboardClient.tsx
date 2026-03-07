"use client";

import { DashboardHeader } from "@/components/dashboard/DashboardHeader";
import { CriticalAlertsPanel } from "@/components/dashboard/CriticalAlertsPanel";
import { HealthAnalyticsSection } from "@/components/dashboard/HealthAnalyticsSection";
import { TimelineSection } from "@/components/dashboard/TimelineSection";
import { AIAssistantCard } from "@/components/dashboard/AIAssistantCard";
import { QuickVitalEntry } from "@/components/dashboard/QuickVitalEntry";
import { OperationsSnapshot } from "@/components/dashboard/OperationsSnapshot";
import { ComplianceNotice } from "@/components/dashboard/ComplianceNotice";
import { DashboardSkeleton } from "@/components/dashboard/DashboardSkeleton";
import {
  useAlerts,
  useAnalytics,
  useAppointments,
  useLabs,
  useMedications,
  useProfile,
  useTimeline,
} from "@/lib/hooks/useDashboardData";

function ErrorBanner({ message }: { message: string }) {
  return (
    <p className="rounded-xl border border-red-200 bg-red-50 px-3 py-2 text-sm text-red-700" role="alert">
      {message}
    </p>
  );
}

export function DashboardClient() {
  const profileQuery = useProfile();
  const patientId = profileQuery.data?.patient.id;

  const alertsQuery = useAlerts(patientId);
  const appointmentsQuery = useAppointments(patientId);
  const medicationsQuery = useMedications(patientId);
  const labsQuery = useLabs(patientId);
  const analyticsQuery = useAnalytics(patientId);
  const timelineQuery = useTimeline(patientId);

  if (profileQuery.isLoading) {
    return <DashboardSkeleton />;
  }

  if (profileQuery.error || !profileQuery.data) {
    return <ErrorBanner message={(profileQuery.error as Error)?.message || "Unable to load patient profile."} />;
  }

  const patient = profileQuery.data.patient;
  const stats = profileQuery.data.stats;
  const disclaimers = profileQuery.data.disclaimers;

  const alerts = alertsQuery.data?.alerts ?? [];
  const appointments = appointmentsQuery.data?.appointments ?? [];
  const medications = medicationsQuery.data?.medications ?? [];
  const labs = labsQuery.data?.labResults ?? [];
  const trends = analyticsQuery.data?.trends ?? [];
  const summary =
    analyticsQuery.data?.summary ??
    ({
      averageHeartRate: null,
      averageSystolic: null,
      averageDiastolic: null,
      averageGlucose: null,
      readingsCount: 0,
    } as const);
  const timelineEvents = timelineQuery.data?.events ?? [];

  return (
    <div className="space-y-4 pb-10">
      <DashboardHeader patientName={patient.fullName} stats={stats} />

      {(alertsQuery.error || appointmentsQuery.error || medicationsQuery.error || labsQuery.error || analyticsQuery.error || timelineQuery.error) && (
        <ErrorBanner
          message={
            (alertsQuery.error as Error)?.message ||
            (appointmentsQuery.error as Error)?.message ||
            (medicationsQuery.error as Error)?.message ||
            (labsQuery.error as Error)?.message ||
            (analyticsQuery.error as Error)?.message ||
            (timelineQuery.error as Error)?.message ||
            "Some dashboard modules failed to load."
          }
        />
      )}

      <CriticalAlertsPanel alerts={alerts} />

      <OperationsSnapshot appointments={appointments} medications={medications} labs={labs} />

      <div className="grid gap-4 xl:grid-cols-3">
        <div className="xl:col-span-2">
          <HealthAnalyticsSection trends={trends} summary={summary} />
        </div>
        <div className="space-y-4">
          <QuickVitalEntry patientId={patient.id} />
          <AIAssistantCard patientId={patient.id} />
        </div>
      </div>

      <TimelineSection events={timelineEvents} />

      <ComplianceNotice disclaimers={disclaimers} />
    </div>
  );
}
