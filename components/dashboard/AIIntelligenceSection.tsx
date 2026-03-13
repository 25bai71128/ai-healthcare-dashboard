"use client";

import {
  CartesianGrid,
  Legend,
  ResponsiveContainer,
  Scatter,
  ScatterChart,
  Tooltip,
  XAxis,
  YAxis,
} from "recharts";
import { SectionCard } from "@/components/ui/SectionCard";
import { useClusterAnalysis, useTreatmentRecommendation } from "@/lib/hooks/useDashboardData";

const CLUSTER_COLORS = ["#0f6bff", "#059669", "#d97706", "#7c3aed", "#0ea5e9", "#db2777"];

function clusterColor(clusterId: number) {
  return CLUSTER_COLORS[Math.abs(clusterId) % CLUSTER_COLORS.length] ?? "#0f6bff";
}

export function AIIntelligenceSection({ patientId }: { patientId: string }) {
  const clusterQuery = useClusterAnalysis(patientId);
  const treatmentQuery = useTreatmentRecommendation(patientId);

  const projection = clusterQuery.data?.clustering.projection ?? [];
  const anomalies = clusterQuery.data?.clustering.anomalies ?? [];
  const measuredAt = clusterQuery.data?.source.measuredAtByIndex ?? [];

  const clusterIds = Array.from(new Set(projection.map((point) => point.cluster))).sort((a, b) => a - b);

  return (
    <SectionCard className="space-y-5" aria-label="AI intelligence">
      <div>
        <h2 className="text-lg font-bold text-slate-900">AI Intelligence</h2>
        <p className="text-sm text-slate-600">
          Unsupervised pattern discovery (clustering + anomaly detection) and a simulation-based treatment optimization policy.
        </p>
      </div>

      <div className="grid gap-4 lg:grid-cols-3">
        <div className="lg:col-span-2">
          <div className="rounded-xl border border-slate-200 bg-white p-4">
            <div className="mb-3 flex items-start justify-between gap-3">
              <div>
                <h3 className="text-sm font-semibold text-slate-900">Vitals Clustering</h3>
                <p className="text-xs text-slate-600">PCA projection colored by K-Means cluster; DBSCAN flags anomalies.</p>
              </div>
              {clusterQuery.isLoading ? (
                <span className="text-xs text-slate-500">Loading…</span>
              ) : clusterQuery.error ? (
                <span className="text-xs text-red-700">{(clusterQuery.error as Error).message}</span>
              ) : (
                <span className="text-xs text-slate-500">{projection.length} points</span>
              )}
            </div>

            <div className="h-[320px] w-full" role="img" aria-label="Clustering scatter plot">
              {projection.length < 3 ? (
                <div className="flex h-full items-center justify-center rounded-lg bg-slate-50 text-sm text-slate-600">
                  Not enough vitals data to compute clusters.
                </div>
              ) : (
                <ResponsiveContainer width="100%" height="100%">
                  <ScatterChart margin={{ top: 8, right: 12, left: 0, bottom: 8 }}>
                    <CartesianGrid strokeDasharray="3 3" stroke="#e2e8f0" />
                    <XAxis type="number" dataKey="x" tick={{ fontSize: 12 }} />
                    <YAxis type="number" dataKey="y" tick={{ fontSize: 12 }} />
                    <Tooltip
                      cursor={{ strokeDasharray: "3 3" }}
                      formatter={(value: number, name: string) => {
                        if (name === "x" || name === "y") {
                          return [Number(value).toFixed(3), name.toUpperCase()];
                        }
                        return [String(value), name];
                      }}
                      labelFormatter={() => ""}
                    />
                    <Legend />
                    {clusterIds.map((clusterId) => (
                      <Scatter
                        key={`cluster-${clusterId}`}
                        name={`Cluster ${clusterId}`}
                        data={projection.filter((point) => point.cluster === clusterId && !point.anomaly)}
                        fill={clusterColor(clusterId)}
                      />
                    ))}
                    <Scatter
                      name="Anomaly"
                      data={projection.filter((point) => point.anomaly)}
                      fill="#ef4444"
                      shape="diamond"
                    />
                  </ScatterChart>
                </ResponsiveContainer>
              )}
            </div>

            <div className="mt-4 grid gap-3 sm:grid-cols-2">
              <div className="rounded-lg border border-slate-200 bg-slate-50 p-3">
                <p className="text-xs font-semibold uppercase tracking-wide text-slate-500">Anomaly Alerts</p>
                {clusterQuery.isLoading ? (
                  <p className="mt-1 text-sm text-slate-600">Loading…</p>
                ) : anomalies.length === 0 ? (
                  <p className="mt-1 text-sm text-slate-600">No anomalies detected in the sampled vitals.</p>
                ) : (
                  <ul className="mt-2 space-y-2">
                    {anomalies.slice(0, 4).map((entry) => (
                      <li key={`anomaly-${entry.index}`} className="rounded-md border border-red-200 bg-red-50 px-2 py-1 text-xs text-red-800">
                        <span className="font-semibold">#{entry.index}</span>
                        {measuredAt[entry.index] ? <span className="ml-2 text-red-700">{measuredAt[entry.index]}</span> : null}
                      </li>
                    ))}
                  </ul>
                )}
              </div>
              <div className="rounded-lg border border-slate-200 bg-slate-50 p-3">
                <p className="text-xs font-semibold uppercase tracking-wide text-slate-500">Cluster Profiles</p>
                <p className="mt-1 text-sm text-slate-600">
                  {clusterQuery.data
                    ? `${Object.keys(clusterQuery.data.clustering.cluster_profiles).length} cluster centroid profiles available.`
                    : "Run clustering to see per-cluster averages."}
                </p>
              </div>
            </div>
          </div>
        </div>

        <div className="space-y-4">
          <div className="rounded-xl border border-slate-200 bg-white p-4">
            <div className="mb-2 flex items-start justify-between gap-3">
              <div>
                <h3 className="text-sm font-semibold text-slate-900">Treatment Strategy</h3>
                <p className="text-xs text-slate-600">Q-learning policy output (simulation-only).</p>
              </div>
              {treatmentQuery.isLoading ? (
                <span className="text-xs text-slate-500">Loading…</span>
              ) : treatmentQuery.error ? (
                <span className="text-xs text-red-700">{(treatmentQuery.error as Error).message}</span>
              ) : null}
            </div>

            {treatmentQuery.data ? (
              <div className="space-y-3">
                <div className="rounded-lg border border-slate-200 bg-slate-50 p-3">
                  <p className="text-xs font-semibold uppercase tracking-wide text-slate-500">Recommendation</p>
                  <p className="mt-1 text-base font-bold text-slate-900">{treatmentQuery.data.recommendation.recommended_treatment}</p>
                  <p className="mt-1 text-xs text-slate-600">Expected outcome score: {treatmentQuery.data.recommendation.expected_outcome_score}</p>
                </div>

                <div className="grid gap-3 sm:grid-cols-2">
                  <div className="rounded-lg border border-slate-200 bg-white p-3">
                    <p className="text-xs font-semibold uppercase tracking-wide text-slate-500">Risk Before</p>
                    <p className="mt-1 text-lg font-bold text-slate-900">{treatmentQuery.data.recommendation.risk_before}</p>
                  </div>
                  <div className="rounded-lg border border-slate-200 bg-white p-3">
                    <p className="text-xs font-semibold uppercase tracking-wide text-slate-500">Risk After</p>
                    <p className="mt-1 text-lg font-bold text-slate-900">{treatmentQuery.data.recommendation.risk_after}</p>
                  </div>
                </div>

                <p className="text-xs text-slate-600">{treatmentQuery.data.recommendation.notes}</p>
              </div>
            ) : (
              <p className="text-sm text-slate-600">No recommendation available yet.</p>
            )}
          </div>
        </div>
      </div>
    </SectionCard>
  );
}
