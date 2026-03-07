export type Severity = "critical" | "warning";

export type AlertType = "UPCOMING_APPOINTMENT" | "OVERDUE_MEDICATION" | "ABNORMAL_VITAL";

export interface CriticalAlert {
  id: string;
  type: AlertType;
  severity: Severity;
  title: string;
  description: string;
  timestamp: string;
  icon: "calendar" | "pill" | "heart";
}

export interface DashboardTimelineEvent {
  id: string;
  kind: "appointment" | "medication" | "lab";
  title: string;
  subtitle: string;
  timestamp: string;
  status: "normal" | "warning" | "critical";
}

export interface VitalTrendPoint {
  measuredAt: string;
  heartRate: number | null;
  systolic: number | null;
  diastolic: number | null;
  glucose: number | null;
}
