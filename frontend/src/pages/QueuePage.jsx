import { useEffect, useMemo, useState } from "react";
import { Link as RouterLink } from "react-router-dom";
import {
  Alert,
  Box,
  Card,
  Chip,
  InputAdornment,
  LinearProgress,
  Stack,
  Table,
  TableBody,
  TableCell,
  TableContainer,
  TableHead,
  TableRow,
  TextField,
  Typography,
  Link,
  MenuItem,
} from "@mui/material";
import SearchIcon from "@mui/icons-material/Search";
import PersonIcon from "@mui/icons-material/Person";
import EmergencyIcon from "@mui/icons-material/WarningAmber";
import HourglassBottomIcon from "@mui/icons-material/HourglassBottom";
import MonitoringIcon from "@mui/icons-material/MonitorHeart";
import { api } from "../api";
import { RiskChip, TriageChip } from "../components/chips";
import { riskColors } from "../theme";

function StatCard({ icon, label, value, color }) {
  return (
    <Card sx={{ p: 2, display: "flex", alignItems: "center", gap: 2 }}>
      <Box
        sx={{
          width: 44,
          height: 44,
          borderRadius: 2,
          display: "grid",
          placeItems: "center",
          background: `${color}14`,
          color,
        }}
      >
        {icon}
      </Box>
      <Box>
        <Typography variant="h5" sx={{ lineHeight: 1.1 }}>
          {value}
        </Typography>
        <Typography variant="body2" color="text.secondary">
          {label}
        </Typography>
      </Box>
    </Card>
  );
}

const BAND_ORDER = { high: 0, elevated: 1, watch: 2, low: 3, unknown: 4 };

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
        if (!cancelled) {
          setData(q);
          setError(null);
        }
      } catch (err) {
        if (!cancelled) setError(err.message);
      }
    })();
    return () => {
      cancelled = true;
    };
  }, [lastEvent]);

  const items = useMemo(() => {
    let rows = data?.items ?? [];
    if (query.trim()) {
      const needle = query.trim().toLowerCase();
      rows = rows.filter((r) => r.patient_id.toLowerCase().includes(needle));
    }
    if (bandFilter !== "all") {
      rows = rows.filter((r) => (r.latest_risk_band ?? "unknown") === bandFilter);
    }
    return [...rows].sort((a, b) => {
      const ba = BAND_ORDER[a.latest_risk_band ?? "unknown"];
      const bb = BAND_ORDER[b.latest_risk_band ?? "unknown"];
      if (ba !== bb) return ba - bb;
      if ((b.open_alert_count ?? 0) !== (a.open_alert_count ?? 0))
        return (b.open_alert_count ?? 0) - (a.open_alert_count ?? 0);
      const ta = a.triage_category ?? 5;
      const tb = b.triage_category ?? 5;
      if (ta !== tb) return ta - tb;
      return a.patient_id.localeCompare(b.patient_id);
    });
  }, [data, query, bandFilter]);

  const highCount = (data?.items ?? []).filter((i) => i.latest_risk_band === "high").length;
  const pendingRecs = (data?.items ?? []).filter((i) => i.pending_recommendation).length;
  const lowConf = (data?.items ?? []).filter((i) => i.latest_assessment_low_confidence).length;

  return (
    <Stack spacing={2.5}>
      <Stack direction={{ xs: "column", md: "row" }} spacing={2}>
        <StatCard
          icon={<PersonIcon />}
          label="Patients in queue"
          value={data?.items?.length ?? "–"}
          color="#2563eb"
        />
        <StatCard icon={<EmergencyIcon />} label="High risk now" value={highCount} color="#dc2626" />
        <StatCard
          icon={<MonitoringIcon />}
          label="Pending recommendations"
          value={pendingRecs}
          color="#7c3aed"
        />
        <StatCard icon={<HourglassBottomIcon />} label="Low-confidence scores" value={lowConf} color="#d97706" />
      </Stack>

      {error && <Alert severity="error">{error}</Alert>}

      <Card>
        <Stack
          direction={{ xs: "column", sm: "row" }}
          spacing={1.5}
          sx={{ p: 2, pb: 1.5, alignItems: { sm: "center" } }}
        >
          <Typography variant="h6" sx={{ flex: 1 }}>
            Live patient queue
          </Typography>
          <TextField
            size="small"
            placeholder="Search patient…"
            value={query}
            onChange={(e) => setQuery(e.target.value)}
            slotProps={{
              input: {
                startAdornment: (
                  <InputAdornment position="start">
                    <SearchIcon fontSize="small" />
                  </InputAdornment>
                ),
              },
            }}
            sx={{ width: 220 }}
          />
          <TextField
            size="small"
            select
            value={bandFilter}
            onChange={(e) => setBandFilter(e.target.value)}
            sx={{ width: 160 }}
          >
            <MenuItem value="all">All risk bands</MenuItem>
            <MenuItem value="high">High</MenuItem>
            <MenuItem value="elevated">Elevated</MenuItem>
            <MenuItem value="watch">Watch</MenuItem>
            <MenuItem value="low">Low</MenuItem>
            <MenuItem value="unknown">No score</MenuItem>
          </TextField>
        </Stack>
        {!data && <LinearProgress />}
        {data && (
          <TableContainer>
            <Table size="small">
              <TableHead>
                <TableRow>
                  <TableCell>Patient</TableCell>
                  <TableCell>ESI</TableCell>
                  <TableCell>Risk</TableCell>
                  <TableCell>Band</TableCell>
                  <TableCell>Latest assessment</TableCell>
                  <TableCell>Open alerts</TableCell>
                  <TableCell>Pending recommendation</TableCell>
                </TableRow>
              </TableHead>
              <TableBody>
                {items.map((row) => (
                  <TableRow key={row.patient_id} hover sx={{ cursor: "pointer" }}>
                    <TableCell>
                      <Link
                        component={RouterLink}
                        to={`/patients/${encodeURIComponent(row.patient_id)}`}
                        underline="hover"
                        fontWeight={700}
                      >
                        {row.patient_id}
                      </Link>
                    </TableCell>
                    <TableCell>
                      <TriageChip category={row.triage_category} />
                    </TableCell>
                    <TableCell>
                      {row.latest_risk_score != null && !row.latest_assessment_stale
                        ? (row.latest_risk_score * 100).toFixed(0)
                        : "—"}
                    </TableCell>
                    <TableCell>
                      <RiskChip
                        band={row.latest_risk_band}
                        score={row.latest_risk_score}
                        stale={row.latest_assessment_stale}
                        lowConfidence={row.latest_assessment_low_confidence}
                      />
                    </TableCell>
                    <TableCell>
                      <Typography variant="body2" color="text.secondary">
                        {row.latest_assessment_status}
                        {row.latest_assessment_at
                          ? ` · ${new Date(row.latest_assessment_at).toLocaleTimeString()}`
                          : ""}
                      </Typography>
                    </TableCell>
                    <TableCell>
                      {row.open_alert_count > 0 ? (
                        <Chip
                          size="small"
                          label={row.open_alert_count}
                          sx={{
                            bgcolor: `${riskColors.high}14`,
                            color: riskColors.high,
                            border: `1px solid ${riskColors.high}40`,
                            fontWeight: 700,
                          }}
                        />
                      ) : (
                        <Typography variant="body2" color="text.secondary">
                          0
                        </Typography>
                      )}
                    </TableCell>
                    <TableCell>
                      {row.pending_recommendation ? (
                        <Chip
                          size="small"
                          label={`ESI ${row.pending_recommendation.current_priority} → ${row.pending_recommendation.proposed_priority}`}
                          color="primary"
                          variant="outlined"
                        />
                      ) : (
                        <Typography variant="body2" color="text.secondary">
                          —
                        </Typography>
                      )}
                    </TableCell>
                  </TableRow>
                ))}
                {items.length === 0 && (
                  <TableRow>
                    <TableCell colSpan={7} align="center" sx={{ py: 4, color: "text.secondary" }}>
                      No patients match.
                    </TableCell>
                  </TableRow>
                )}
              </TableBody>
            </Table>
          </TableContainer>
        )}
      </Card>
    </Stack>
  );
}
