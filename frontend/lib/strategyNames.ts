const STRATEGY_LABELS: Record<string, string> = {
  swing_v2_1: "SectorEdge 10",
  swing_v2_1_rolling_10_slot: "SectorEdge 10",
  sector_rotation_adx_1m3m: "SectorEdge 10",
  sector_rotation_adx_r10_vwap25: "SectorEdge 10",
  swing_v2_1_sector_1m3m_40_60: "SectorEdge 10",
  rolling10_1m3m_vwap25_paper: "SectorEdge 10"
};

export function strategyLabel(value: string | null | undefined): string {
  if (!value) return "n/a";
  return STRATEGY_LABELS[value] || value;
}

export function recommendationModelFromSearch(searchParams?: Record<string, string | string[] | undefined>): string {
  const raw = searchParams?.model || searchParams?.recommendation_type;
  const value = Array.isArray(raw) ? raw[0] : raw;
  return value || "sector_rotation_adx_1m3m";
}
