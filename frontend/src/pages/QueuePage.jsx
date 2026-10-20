import { useEffect, useMemo, useState } from "react";
import { Link as RouterLink } from "react-router-dom";
import {
  Alert, Box, Card, Chip, InputAdornment, LinearProgress, Stack, Table,
  TableBody, TableCell, TableContainer, TableHead, TableRow, TextField,
  Typography, Link, MenuItem,
} from "@mui/material";
import SearchIcon from "@mui/icons-material/Search";
import EmergencyIcon from "@mui/icons-material/WarningAmber";
import HourglassBottomIcon from "@mui/icons-material/HourglassBottom";
import MonitoringIcon from "@mui/icons-material/MonitorHeart";
import GroupsIcon from "@mui/icons-material/Groups";
import AccessTimeIcon from "@mui/icons-material/AccessTime";
import ShieldOutlinedIcon from "@mui/icons-material/ShieldOutlined";
import { api } from "../api";
import { RiskChip, TriageChip } from "../components/chips";
import { riskColors } from "../theme";

function StatCard({ icon, label, value, color, hint }) {
  return (
    <Card sx={{
      p: { xs: 1.75, sm: 2.25 }, display: "flex", alignItems: "center", gap: 1.75,
      minWidth: 0, position: "relative", overflow: "hidden",
      "&:hover": { borderColor: "#cbd5e1", boxShadow: "0 9px 24px rgba(16,24,40,0.07)", transform: "translateY(-2px)" },
      "&::after": { content: '""', position: "absolute", right: -22, top: -28, width: 90, height: 90, borderRadius: "50%", background: color, opacity: 0.055, pointerEvents: "none" },
    }}>
      <Box sx={{ width: 46, height: 46, flexShrink: 0, borderRadius: 2.5, display: "grid", placeItems: "center", background: `${color}12`, color }}>
        {icon}
      </Box>
      <Box sx={{ minWidth: 0 }}>
        <Typography variant="h5" sx={{ lineHeight: 1.15, fontSize: { xs: 23, sm: 27 }, fontVariantNumeric: "tabular-nums" }}>{value}</Typography>
        <Typography sx={{ fontSize: 12.5, color: "text.secondary", mt: 0.55, fontWeight: 600, lineHeight: 1.35 }}>{label}</Typography>
        {hint && <Typography sx={{ fontSize: 10.5, color: "text.secondary", mt: 0.45 }}>{hint}</Typography>}
      </Box>
    </Card>
  );
}

const BAND_ORDER = { high: 0, elevated: 1, watch: 2, low: 3, unknown: 4 };
const formatTime = (value) => value ? new Date(value).toLocaleTimeString([], { hour: "2-digit", minute: "2-digit" }) : "—";

export default function QueuePage({ lastEvent }) {
  const [data, setData] = useState(null);
  const [error, setError] = useState(null);
  const [query, setQuery] = useState("");
  const [bandFilter, setBandFilter] = useState("all");

  useEffect(() => {
    let cancelled = false;
    (async () => {
      try {
        const q = await api.queue();
        if (!cancelled) { setData(q); setError(null); }
      } catch (err) {
        if (!cancelled) setError(err.message);
      }
    })();
    return () => { cancelled = true; };
  }, [lastEvent]);

  const allItems = data?.items ?? [];
  const items = useMemo(() => {
    let rows = allItems;
    if (query.trim()) {
      const needle = query.trim().toLowerCase();
      rows = rows.filter((r) => String(r.patient_id ?? "").toLowerCase().includes(needle));
    }
    if (bandFilter !== "all") rows = rows.filter((r) => (r.latest_risk_band ?? "unknown") === bandFilter);
    return [...rows].sort((a, b) => {
      const ba = BAND_ORDER[a.latest_risk_band ?? "unknown"];
      const bb = BAND_ORDER[b.latest_risk_band ?? "unknown"];
      if (ba !== bb) return ba - bb;
      if ((b.open_alert_count ?? 0) !== (a.open_alert_count ?? 0)) return (b.open_alert_count ?? 0) - (a.open_alert_count ?? 0);
      const ta = a.triage_category ?? 5;
      const tb = b.triage_category ?? 5;
      if (ta !== tb) return ta - tb;
      return String(a.patient_id).localeCompare(String(b.patient_id));
    });
  }, [allItems, query, bandFilter]);

  const highCount = allItems.filter((i) => i.latest_risk_band === "high").length;
  const pendingRecs = allItems.filter((i) => i.pending_recommendation).length;
  const lowConf = allItems.filter((i) => i.latest_assessment_low_confidence).length;
  const openAlerts = allItems.reduce((sum, item) => sum + (item.open_alert_count ?? 0), 0);

  return (
    <Stack spacing={2.5}>
      <Box sx={{ display: "flex", alignItems: { xs: "flex-start", sm: "center" }, justifyContent: "space-between", flexWrap: "wrap", gap: 1.5 }}>
        <Box>
          <Stack direction="row" alignItems="center" spacing={1} sx={{ mb: 0.7 }}>
            <Typography variant="overline" sx={{ color: "primary.main" }}>CLINICAL OPERATIONS</Typography>
            <Box sx={{ width: 5, height: 5, borderRadius: "50%", bgcolor: "#16a34a" }} />
            <Typography sx={{ fontSize: 10.5, color: "text.secondary", fontWeight: 700 }}>LIVE VIEW</Typography>
          </Stack>
          <Typography variant="h4" sx={{ fontSize: { xs: 25, sm: 30 }, lineHeight: 1.2 }}>Patient overview</Typography>
          <Typography color="text.secondary" sx={{ mt: 0.75, fontSize: 13.5 }}>Prioritize review with current observations, risk signals and clinician decisions.</Typography>
        </Box>
        <Chip icon={<AccessTimeIcon />} label={data?.generated_at ? `Updated ${formatTime(data.generated_at)}` : "Waiting for first update"} variant="outlined" sx={{ bgcolor: "#fff", borderColor: "divider", color: "text.secondary", fontWeight: 650 }} />
      </Box>

      <Box sx={{ display: "grid", gridTemplateColumns: { xs: "repeat(2,minmax(0,1fr))", xl: "repeat(4,minmax(0,1fr))" }, gap: 1.5 }}>
        <StatCard icon={<GroupsIcon />} label="Patients in queue" value={data ? allItems.length : "—"} color="#5E0ED7" hint="Current active cohort" />
        <StatCard icon={<EmergencyIcon />} label="High risk now" value={data ? highCount : "—"} color="#b91c1c" hint="Requires clinician review" />
        <StatCard icon={<MonitoringIcon />} label="Pending decisions" value={data ? pendingRecs : "—"} color="#9333EA" hint="Recommendations awaiting review" />
        <StatCard icon={<HourglassBottomIcon />} label="Low-confidence scores" value={data ? lowConf : "—"} color="#b45309" hint="Interpret with added caution" />
      </Box>

      {error && <Alert severity="error" action={<Chip size="small" label="Connection issue" color="error" variant="outlined" />}>{error}</Alert>}
      {data && highCount > 0 && (
        <Alert severity="warning" icon={<EmergencyIcon />} sx={{ borderRadius: 2.5, alignItems: "center", "& .MuiAlert-message": { py: 0.25 } }}>
          <Typography component="span" sx={{ fontWeight: 800 }}>{highCount} patient{highCount === 1 ? "" : "s"} with a high-risk signal.</Typography>
          {" "}Review the latest observations and clinical context; this score is not a diagnosis.
        </Alert>
      )}

      <Card sx={{ overflow: "hidden" }}>
        <Box sx={{ p: { xs: 1.75, sm: 2.5 }, pb: 2, display: "flex", flexWrap: "wrap", alignItems: "center", gap: 1.5 }}>
          <Box sx={{ flex: "1 1 220px", minWidth: 0 }}>
            <Stack direction="row" alignItems="center" spacing={1}>
              <Typography variant="h6" sx={{ fontSize: 17 }}>Live patient queue</Typography>
              <Chip size="small" label={allItems.length} sx={{ height: 23, bgcolor: "#F4EFFC", color: "#5E0ED7", fontWeight: 800 }} />
            </Stack>
            <Typography variant="body2" color="text.secondary" sx={{ fontSize: 12, mt: 0.4 }}>Sorted by risk signal, open alerts and triage category.</Typography>
          </Box>
          <TextField
            placeholder="Find patient ID…"
            value={query}
            onChange={(e) => setQuery(e.target.value)}
            sx={{ width: { xs: "100%", sm: 210 } }}
            slotProps={{ input: { startAdornment: <InputAdornment position="start"><SearchIcon fontSize="small" /></InputAdornment> } }}
            inputProps={{ "aria-label": "Search patient ID" }}
          />
          <TextField select value={bandFilter} onChange={(e) => setBandFilter(e.target.value)} sx={{ width: { xs: "100%", sm: 160 } }} inputProps={{ "aria-label": "Filter by risk band" }}>
            <MenuItem value="all">All risk bands</MenuItem>
            <MenuItem value="high">High</MenuItem>
            <MenuItem value="elevated">Elevated</MenuItem>
            <MenuItem value="watch">Watch</MenuItem>
            <MenuItem value="low">Low</MenuItem>
            <MenuItem value="unknown">No score</MenuItem>
          </TextField>
        </Box>
        <DividerLine />
        {!data && <LinearProgress />}
        {data && (
          <>
            <TableContainer sx={{ overflowX: "auto" }}>
              <Table size="small" sx={{ minWidth: 900 }}>
                <TableHead>
                  <TableRow>
                    <TableCell>Patient</TableCell>
                    <TableCell>ESI</TableCell>
                    <TableCell>Risk score</TableCell>
                    <TableCell>Risk band</TableCell>
                    <TableCell>Latest assessment</TableCell>
                    <TableCell>Open alerts</TableCell>
                    <TableCell>Pending recommendation</TableCell>
                  </TableRow>
                </TableHead>
                <TableBody>
                  {items.map((row) => (
                    <TableRow key={row.patient_id} hover>
                      <TableCell>
                        <Link component={RouterLink} to={`/patients/${encodeURIComponent(row.patient_id)}`} underline="hover" fontWeight={750} sx={{ color: "#5E0ED7" }}>
                          {row.patient_id}
                        </Link>
                        <Typography variant="caption" display="block" color="text.secondary" sx={{ mt: 0.25 }}>Patient record</Typography>
                      </TableCell>
                      <TableCell><TriageChip category={row.triage_category} /></TableCell>
                      <TableCell>
                        <Typography sx={{ fontWeight: 800, fontVariantNumeric: "tabular-nums", color: row.latest_risk_score != null && !row.latest_assessment_stale ? (riskColors[row.latest_risk_band] ?? "text.primary") : "text.secondary" }}>
                          {row.latest_risk_score != null && !row.latest_assessment_stale ? `${(row.latest_risk_score * 100).toFixed(0)}%` : "—"}
                        </Typography>
                      </TableCell>
                      <TableCell><RiskChip band={row.latest_risk_band} score={row.latest_risk_score} stale={row.latest_assessment_stale} lowConfidence={row.latest_assessment_low_confidence} /></TableCell>
                      <TableCell>
                        <Typography variant="body2" sx={{ fontWeight: 650 }}>{String(row.latest_assessment_status ?? "unknown").replaceAll("_", " ")}</Typography>
                        <Typography variant="caption" color="text.secondary">{formatTime(row.latest_assessment_at)}</Typography>
                      </TableCell>
                      <TableCell>
                        {row.open_alert_count > 0 ? (
                          <Chip size="small" label={row.open_alert_count} sx={{ bgcolor: "#fef2f2", color: riskColors.high, border: "1px solid #fecaca", fontWeight: 800 }} />
                        ) : <Typography variant="body2" color="text.secondary">0</Typography>}
                      </TableCell>
                      <TableCell>
                        {row.pending_recommendation ? (
                          <Chip size="small" label={`ESI ${row.pending_recommendation.current_priority} → ${row.pending_recommendation.proposed_priority}`} color="primary" variant="outlined" />
                        ) : <Typography variant="body2" color="text.secondary">No action pending</Typography>}
                      </TableCell>
                    </TableRow>
                  ))}
                  {items.length === 0 && (
                    <TableRow><TableCell colSpan={7} align="center" sx={{ py: 6 }}>
                      <Box sx={{ display: "grid", justifyItems: "center", gap: 1 }}>
                        <ShieldOutlinedIcon sx={{ fontSize: 32, color: "text.disabled" }} />
                        <Typography fontWeight={750}>{allItems.length ? "No matching patients" : "No patients in the queue"}</Typography>
                        <Typography variant="body2" color="text.secondary">{allItems.length ? "Try changing the search or risk-band filter." : "Patients will appear here when data is received."}</Typography>
                      </Box>
                    </TableCell></TableRow>
                  )}
                </TableBody>
              </Table>
            </TableContainer>
            <Box sx={{ px: 2.5, py: 1.5, display: "flex", alignItems: "center", justifyContent: "space-between", gap: 1, flexWrap: "wrap", borderTop: "1px solid", borderColor: "divider", bgcolor: "#fcfdff" }}>
              <Typography variant="caption" color="text.secondary">Showing {items.length} of {allItems.length} patients</Typography>
              <Stack direction="row" alignItems="center" spacing={0.75}>
                <Box sx={{ width: 6, height: 6, borderRadius: "50%", bgcolor: "#16a34a" }} />
                <Typography variant="caption" color="text.secondary">{openAlerts} open alert{openAlerts === 1 ? "" : "s"} across queue</Typography>
              </Stack>
            </Box>
          </>
        )}
      </Card>
      <Stack direction="row" spacing={1} alignItems="flex-start" sx={{ px: 0.5 }}>
        <ShieldOutlinedIcon sx={{ fontSize: 16, color: "text.secondary", mt: 0.15 }} />
        <Typography variant="caption" color="text.secondary" sx={{ lineHeight: 1.6 }}>
          Research decision-support prototype. Risk scores can be uncertain or stale and must be interpreted with patient context. Clinicians retain responsibility for all triage and treatment decisions.
        </Typography>
      </Stack>
    </Stack>
  );
}

function DividerLine() {
  return <Box sx={{ height: "1px", bgcolor: "divider" }} />;
}
