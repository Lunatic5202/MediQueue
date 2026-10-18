import { riskColors } from "../theme";

const BAND_LABELS = { low: "Low", watch: "Watch", elevated: "Elevated", high: "High" };
const SEV_COLORS = { watch: riskColors.watch, elevated: riskColors.elevated, high: riskColors.high };

export function riskBadgeStyle(band) {
  const color = riskColors[band] ?? riskColors.unknown;
  return {
    backgroundColor: `${color}1a`,
    color,
    border: `1px solid ${color}40`,
    borderRadius: "999px",
    padding: "2px 10px",
    fontSize: 12,
    fontWeight: 700,
    display: "inline-flex",
    alignItems: "center",
    gap: 6,
  };
}

export function RiskChip({ band, score, stale, lowConfidence }) {
  const label = BAND_LABELS[band] ?? "No score";
  const color = riskColors[band] ?? riskColors.unknown;
  return (
    <span style={riskBadgeStyle(band ?? "unknown")}>
      <span style={{ width: 7, height: 7, borderRadius: "50%", background: color }} />
      {label}
      {score != null && !stale && (
        <span style={{ fontWeight: 600, opacity: 0.8 }}>{(score * 100).toFixed(0)}</span>
      )}
      {stale && <span style={{ fontWeight: 700 }}>STALE</span>}
      {!stale && lowConfidence && <span style={{ fontWeight: 700 }}>LOW CONF</span>}
    </span>
  );
}

export function SeverityChip({ severity }) {
  const color = SEV_COLORS[severity] ?? "#64748b";
  return (
    <span
      style={{
        backgroundColor: `${color}1a`,
        color,
        border: `1px solid ${color}40`,
        borderRadius: "999px",
        padding: "2px 10px",
        fontSize: 12,
        fontWeight: 700,
        textTransform: "capitalize",
      }}
    >
      {severity}
    </span>
  );
}

export function StatusChip({ status }) {
  const map = {
    pending: { c: "#2563eb", bg: "#2563eb14" },
    confirmed: { c: "#059669", bg: "#05966914" },
    rejected: { c: "#64748b", bg: "#64748b14" },
    overridden: { c: "#7c3aed", bg: "#7c3aed14" },
    superseded: { c: "#94a3b8", bg: "#94a3b814" },
    open: { c: "#dc2626", bg: "#dc262614" },
    suppressed: { c: "#94a3b8", bg: "#94a3b814" },
    resolved: { c: "#059669", bg: "#05966914" },
  };
  const { c, bg } = map[status] ?? { c: "#64748b", bg: "#64748b14" };
  return (
    <span
      style={{
        background: bg,
        color: c,
        border: `1px solid ${c}33`,
        borderRadius: "999px",
        padding: "2px 10px",
        fontSize: 12,
        fontWeight: 700,
        textTransform: "capitalize",
      }}
    >
      {status}
    </span>
  );
}

export function TriageChip({ category }) {
  const colors = { 1: "#dc2626", 2: "#ea580c", 3: "#d97706", 4: "#0891b2", 5: "#059669" };
  const c = colors[category] ?? "#64748b";
  return (
    <span
      style={{
        background: `${c}14`,
        color: c,
        border: `1px solid ${c}40`,
        borderRadius: 8,
        padding: "2px 8px",
        fontWeight: 700,
        fontSize: 12,
      }}
    >
      ESI {category}
    </span>
  );
}
