"use client";

import { useMutation, useQuery, useQueryClient } from "@tanstack/react-query";
import {
  askAssistant,
  createVital,
  getAlerts,
  getAnalytics,
  getAppointments,
  getLabs,
  getMedications,
  getProfile,
  getTimeline,
  getVitals,
} from "@/lib/api/client";

function patientKey(patientId?: string | null) {
  return patientId ?? "primary";
}

export function useProfile(patientId?: string | null) {
  return useQuery({
    queryKey: ["profile", patientKey(patientId)],
    queryFn: () => getProfile(patientId),
  });
}

export function useAlerts(patientId?: string | null) {
  return useQuery({
    queryKey: ["alerts", patientKey(patientId)],
    queryFn: () => getAlerts(patientId),
    refetchInterval: 30_000,
  });
}

export function useAppointments(patientId?: string | null) {
  return useQuery({
    queryKey: ["appointments", patientKey(patientId)],
    queryFn: () => getAppointments(patientId),
    refetchInterval: 60_000,
  });
}

export function useMedications(patientId?: string | null) {
  return useQuery({
    queryKey: ["medications", patientKey(patientId)],
    queryFn: () => getMedications(patientId),
    refetchInterval: 45_000,
  });
}

export function useVitals(patientId?: string | null) {
  return useQuery({
    queryKey: ["vitals", patientKey(patientId)],
    queryFn: () => getVitals(patientId),
    refetchInterval: 30_000,
  });
}

export function useLabs(patientId?: string | null) {
  return useQuery({
    queryKey: ["labs", patientKey(patientId)],
    queryFn: () => getLabs(patientId),
    refetchInterval: 90_000,
  });
}

export function useAnalytics(patientId?: string | null) {
  return useQuery({
    queryKey: ["analytics", patientKey(patientId)],
    queryFn: () => getAnalytics(patientId),
  });
}

export function useTimeline(patientId?: string | null) {
  return useQuery({
    queryKey: ["timeline", patientKey(patientId)],
    queryFn: () => getTimeline(patientId),
  });
}

export function useCreateVital() {
  const queryClient = useQueryClient();

  return useMutation({
    mutationFn: createVital,
    onSuccess: () => {
      queryClient.invalidateQueries({ queryKey: ["vitals"] });
      queryClient.invalidateQueries({ queryKey: ["alerts"] });
      queryClient.invalidateQueries({ queryKey: ["analytics"] });
    },
  });
}

export function useAssistant() {
  return useMutation({
    mutationFn: askAssistant,
  });
}
