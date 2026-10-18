import { useCallback, useEffect, useState } from "react";
import { Link as RouterLink, useParams } from "react-router-dom";
import {
  Alert,
  Box,
  Button,
  Card,
  Chip,
  Dialog,
  DialogActions,
  DialogContent,
  DialogContentText,
  DialogTitle,
  Divider,
  Grid,
  LinearProgress,
  List,
  ListItem,
  ListItemText,
  MenuItem,
  Stack,
  TextField,
  Typography,
  Link,
} from "@mui/material";
import ArrowBackIcon from "@mui/icons-material/ArrowBack";
import {
  CartesianGrid,
  Line,
  LineChart,
  ReferenceArea,
  ResponsiveContainer,
  Tooltip as RTooltip,
  XAxis,
  YAxis,
} from "recharts";
import { api } from "../api";
import { RiskChip, SeverityChip, StatusChip, TriageChip } from "../components/chips";
import { riskColors } from "../theme";

const VITAL_META = {
  heart_rate: { label: "Heart rate", unit: "bpm", color: "#dc2626", domain: [40, 180] },
  spo2: { label: "SpO₂", unit: "%", color: "#2563eb", domain: [80, 100] },
  blood_pressure: { label: "Systolic BP", unit: "mmHg", color: "#7c3aed", domain: [60, 200] },
  temperature: { label: "Temperature", unit: "°C", color: "#d97706", domain: [34, 42] },
};

function VitalChart({ vital, observations }) {
  const meta = VITAL_META[vital];
  const data = observations
    .filter((o) => o.vital_type === vital)
    .map((o) => ({
      t: new Date(o.device_ts).getTime(),
      v: o.value,
      d: o.value_diastolic ?? undefined,
    }))
    .sort((a, b) => a.t - b.t);
  if (!data.length) return null;
  const fmt = (t) =>
    new Date(t).toLocaleTimeString([], { hour: "2-digit", minute: "2-digit", second: "2-digit" });
  return (
    <Card sx={{ p: 2 }}>
      <Stack direction="row" alignItems="center" spacing={1} sx={{ mb: 1 }}>
        <Box sx={{ width: 10, height: 10, borderRadius: "50%", background: meta.color }} />
        <Typography variant="subtitle2">{meta.label}</Typography>
        <Typography variant="caption" color="text.secondary">
          ({meta.unit})
        </Typography>
      </Stack>
      <ResponsiveContainer width="100%" height={160}>
        <LineChart data={data} margin={{ top: 4, right: 8, bottom: 0, left: -18 }}>
          <CartesianGrid strokeDasharray="3 3" stroke="#e2e8f0" />
          <XAxis dataKey="t" tickFormatter={fmt} tick={{ fontSize: 10 }} minTickGap={40} />
          <YAxis domain={meta.domain} tick={{ fontSize: 10 }} />
          <RTooltip labelFormatter={(t) => fmt(t)} formatter={(v, name) => [v, name === "v" ? meta.label : "diastolic"]} />
          <Line type="monotone" dataKey="v" stroke={meta.color} strokeWidth={2} dot={false} />
          {vital === "blood_pressure" && (
            <Line type="monotone" dataKey="d" stroke="#a78bfa" strokeWidth={1.5} strokeDasharray="4 3" dot={false} />
          )}
        </LineChart>
      </ResponsiveContainer>
    </Card>
  );
}

function RiskChart({ assessments }) {
  const data = assessments
    .filter((a) => a.risk_score != null)
    .map((a) => ({ t: new Date(a.created_at).getTime(), s: a.risk_score * 100, stale: a.stale }))
    .sort((a, b) => a.t - b.t);
  const fmt = (t) => new Date(t).toLocaleTimeString([], { hour: "2-digit", minute: "2-digit" });
  return (
    <Card sx={{ p: 2 }}>
      <Typography variant="subtitle2" sx={{ mb: 1 }}>
        Risk score over time
      </Typography>
      {data.length === 0 ? (
        <Typography variant="body2" color="text.secondary">
          No scored assessments yet (insufficient history or inference abstained).
        </Typography>
      ) : (
        <ResponsiveContainer width="100%" height={180}>
          <LineChart data={data} margin={{ top: 4, right: 8, bottom: 0, left: -18 }}>
            <CartesianGrid strokeDasharray="3 3" stroke="#e2e8f0" />
            <ReferenceArea y1={60} y2={100} fill={riskColors.high} fillOpacity={0.05} />
            <XAxis dataKey="t" tickFormatter={fmt} tick={{ fontSize: 10 }} minTickGap={40} />
            <YAxis domain={[0, 100]} tick={{ fontSize: 10 }} />
            <RTooltip
              labelFormatter={(t) => fmt(t)}
              formatter={(v, _n, p) => [`${v.toFixed(0)}${p.payload.stale ? " (stale)" : ""}`, "risk"]}
            />
            <Line type="stepAfter" dataKey="s" stroke="#2563eb" strokeWidth={2} dot={{ r: 2 }} />
          </LineChart>
        </ResponsiveContainer>
      )}
    </Card>
  );
}

export default function PatientPage({ lastEvent, onAction }) {
  const { patientId } = useParams();
  const [patient, setPatient] = useState(null);
  const [history, setHistory] = useState(null);
  const [risk, setRisk] = useState(null);
  const [timeline, setTimeline] = useState(null);
  const [recs, setRecs] = useState([]);
  const [error, setError] = useState(null);

  const [dialog, setDialog] = useState(null); // { kind, rec }
  const [rationale, setRationale] = useState("");
  const [overridePriority, setOverridePriority] = useState(1);
  const [busy, setBusy] = useState(false);

  const load = useCallback(async () => {
    try {
      const [p, h, r, t, recList] = await Promise.all([
        api.patient(patientId),
        api.history(patientId),
        api.risk(patientId),
        api.timeline(patientId),
        api.recommendations({ patient_id: patientId, limit: 50 }),
      ]);
      setPatient(p);
      setHistory(h);
      setRisk(r);
      setTimeline(t);
      setRecs(recList.recommendations ?? []);
      setError(null);
    } catch (err) {
      setError(err.message);
    }
  }, [patientId]);

  useEffect(() => {
    load();
  }, [load, lastEvent]);

  async function submitDialog() {
    if (!dialog) return;
    setBusy(true);
    try {
      const { kind, rec } = dialog;
      if (kind === "confirm") await api.confirm(rec.id, rationale || undefined);
      else if (kind === "reject") await api.reject(rec.id, rationale);
      else if (kind === "override") await api.override(rec.id, overridePriority, rationale);
      setDialog(null);
      setRationale("");
      onAction?.();
      await load();
    } catch (err) {
      setError(err.message);
    } finally {
      setBusy(false);
    }
  }

  if (!patient && !error) return <LinearProgress />;
  if (!patient)
    return (
      <Alert severity="error" action={<Link to="/">Back to queue</Link>}>
        {error}
      </Alert>
    );

  const pending = recs.find((r) => r.status === "pending");
  const observations = history?.observations ?? [];
  const latestFeatures = history?.latest_features ?? {};
  const latest = latestFeatures.features ?? {};
  const deviceTimes = observations.map((o) => new Date(o.device_ts).getTime());
  const spanMinutes = deviceTimes.length
    ? (Math.max(...deviceTimes) - Math.min(...deviceTimes)) / 60000
    : 0;
  const assessments = timeline?.assessments ?? [];

  return (
    <Stack spacing={2.5}>
      <Stack direction="row" spacing={2} alignItems="center">
        <Button component={RouterLink} to="/" startIcon={<ArrowBackIcon />} variant="outlined" size="small">
          Queue
        </Button>
        <Box sx={{ flex: 1 }}>
          <Typography variant="h5">{patient.patient_id}</Typography>
          <Typography variant="body2" color="text.secondary">
            Registered {patient.arrival_time ? new Date(patient.arrival_time).toLocaleString() : "—"} ·{" "}
            {observations.length} observations in window
          </Typography>
        </Box>
        <TriageChip category={patient.triage_category} />
        <RiskChip
          band={risk?.risk_band}
          score={risk?.risk_score}
          stale={risk?.stale}
          lowConfidence={risk?.low_confidence ?? latestFeatures.low_confidence}
        />
      </Stack>

      {error && <Alert severity="warning">{error}</Alert>}
      {risk?.stale && (
        <Alert severity="warning">
          Latest score is stale — inference failed on the most recent observation. Prior score retained, marked stale.
        </Alert>
      )}

      <Grid container spacing={2}>
        <Grid size={{ xs: 12, md: 6 }}>
          <RiskChart assessments={assessments} />
        </Grid>
        {Object.keys(VITAL_META).map((v) => (
          <Grid key={v} size={{ xs: 12, md: 6 }}>
            <VitalChart vital={v} observations={observations} />
          </Grid>
        ))}
      </Grid>

      <Grid container spacing={2}>
        <Grid size={{ xs: 12, md: 5 }}>
          <Card sx={{ p: 2, height: "100%" }}>
            <Typography variant="h6" gutterBottom>
              Latest risk evidence
            </Typography>
            <Divider sx={{ mb: 1.5 }} />
            {risk?.status === "abstained" || risk?.risk_score == null ? (
              <Alert severity="info">
                {risk?.reason === "insufficient_history"
                  ? "Not enough history yet — at least 3 readings spanning 10 minutes required. Score withheld; never displayed as safe."
                  : "No score available."}
              </Alert>
            ) : (
              <List dense>
                <ListItem>
                  <ListItemText primary="Score" secondary={(risk.risk_score * 100).toFixed(1) + " / 100"} />
                </ListItem>
                <ListItem>
                  <ListItemText primary="Model version" secondary={risk.model_version_id ?? "—"} />
                </ListItem>
                <ListItem>
                  <ListItemText
                    primary="Inference latency"
                    secondary={risk.latency_ms != null ? `${risk.latency_ms.toFixed(1)} ms` : "—"}
                  />
                </ListItem>
                <ListItem>
                  <ListItemText
                    primary="Missing vitals (4h window)"
                    secondary={
                      (latestFeatures.missing_vitals ?? []).length
                        ? latestFeatures.missing_vitals.join(", ")
                        : "none"
                    }
                  />
                </ListItem>
                <ListItem>
                  <ListItemText
                    primary="Reading count / span"
                    secondary={`${latest.global__reading_count ?? "—"} readings · ${Math.round(spanMinutes)} min`}
                  />
                </ListItem>
              </List>
            )}
            <Divider sx={{ my: 1.5 }} />
            <Typography variant="subtitle2" gutterBottom>
              Latest vitals
            </Typography>
            <Stack direction="row" flexWrap="wrap" gap={1}>
              {Object.entries(VITAL_META).map(([v, meta]) => {
                const val = latest[`${v}__latest`];
                return (
                  <Chip
                    key={v}
                    size="small"
                    label={`${meta.label}: ${val != null ? val : "—"}`}
                    sx={{ bgcolor: `${meta.color}10`, border: `1px solid ${meta.color}33` }}
                  />
                );
              })}
            </Stack>
          </Card>
        </Grid>

        <Grid size={{ xs: 12, md: 7 }}>
          <Card sx={{ p: 2, height: "100%" }}>
            <Typography variant="h6" gutterBottom>
              Queue recommendations
            </Typography>
            <Divider sx={{ mb: 1.5 }} />
            {pending ? (
              <Stack spacing={2}>
                <Box
                  sx={{
                    p: 2,
                    borderRadius: 2,
                    border: "1px solid #2563eb40",
                    background: "#2563eb0a",
                  }}
                >
                  <Stack direction="row" alignItems="center" spacing={1} sx={{ mb: 1 }}>
                    <Chip size="small" color="primary" label={`ESI ${pending.current_priority} → ${pending.proposed_priority}`} />
                    <StatusChip status={pending.status} />
                    {pending.direction && (
                      <Chip size="small" variant="outlined" label={pending.direction} />
                    )}
                  </Stack>
                  <Typography variant="body2" color="text.secondary" gutterBottom>
                    Created {new Date(pending.created_at).toLocaleTimeString()} · requires clinician decision
                  </Typography>
                  <Stack direction="row" spacing={1} sx={{ mt: 1.5 }}>
                    <Button variant="contained" size="small" onClick={() => setDialog({ kind: "confirm", rec: pending })}>
                      Confirm
                    </Button>
                    <Button
                      variant="outlined"
                      size="small"
                      color="inherit"
                      onClick={() => setDialog({ kind: "reject", rec: pending })}
                    >
                      Reject…
                    </Button>
                    <Button
                      variant="outlined"
                      size="small"
                      color="secondary"
                      onClick={() => setDialog({ kind: "override", rec: pending })}
                    >
                      Override…
                    </Button>
                  </Stack>
                </Box>
              </Stack>
            ) : (
              <Typography variant="body2" color="text.secondary">
                No pending recommendation for this patient.
              </Typography>
            )}

            <Divider sx={{ my: 2 }} />
            <Typography variant="subtitle2" gutterBottom>
              Decision history
            </Typography>
            {recs.length === 0 ? (
              <Typography variant="body2" color="text.secondary">
                No recommendations yet.
              </Typography>
            ) : (
              <List dense>
                {recs.map((r) => (
                  <ListItem key={r.id} divider>
                    <ListItemText
                      primary={
                        <Stack direction="row" spacing={1} alignItems="center">
                          <Typography variant="body2" fontWeight={700}>
                            ESI {r.current_priority} → {r.proposed_priority}
                            {r.applied_priority != null ? ` (applied ${r.applied_priority})` : ""}
                          </Typography>
                          <StatusChip status={r.status} />
                        </Stack>
                      }
                      secondary={
                        <>
                          {r.decided_by ? `${r.decided_by} · ` : ""}
                          {r.decided_at ? new Date(r.decided_at).toLocaleString() : new Date(r.created_at).toLocaleString()}
                          {r.rationale ? ` — “${r.rationale}”` : ""}
                        </>
                      }
                    />
                  </ListItem>
                ))}
              </List>
            )}
          </Card>
        </Grid>

        <Grid size={12}>
          <Card sx={{ p: 2 }}>
            <Typography variant="h6" gutterBottom>
              Alert evidence (structured explanations)
            </Typography>
            <Divider sx={{ mb: 1.5 }} />
            <AlertList patientId={patientId} lastEvent={lastEvent} />
          </Card>
        </Grid>
      </Grid>

      <Dialog open={Boolean(dialog)} onClose={() => setDialog(null)} fullWidth maxWidth="sm">
        <DialogTitle>
          {dialog?.kind === "confirm" && "Confirm recommendation"}
          {dialog?.kind === "reject" && "Reject recommendation"}
          {dialog?.kind === "override" && "Override triage priority"}
        </DialogTitle>
        <DialogContent>
          <DialogContentText sx={{ mb: 2 }}>
            {dialog?.kind === "confirm" &&
              `This applies ESI ${dialog.rec.proposed_priority} (one step from ${dialog.rec.current_priority}). The action is fully audited.`}
            {dialog?.kind === "reject" &&
              "Rejection suppresses the linked alert until the signal materially worsens. A rationale is required."}
            {dialog?.kind === "override" &&
              "Clinician-directed priority. May exceed the automatic one-step bound. Rationale is required."}
          </DialogContentText>
          {dialog?.kind === "override" && (
            <TextField
              select
              label="Override priority"
              value={overridePriority}
              onChange={(e) => setOverridePriority(Number(e.target.value))}
              fullWidth
              sx={{ mb: 2 }}
            >
              {[1, 2, 3, 4, 5].map((p) => (
                <MenuItem key={p} value={p}>
                  ESI {p}
                </MenuItem>
              ))}
            </TextField>
          )}
          <TextField
            label="Rationale"
            value={rationale}
            onChange={(e) => setRationale(e.target.value)}
            fullWidth
            multiline
            minRows={2}
            required={dialog?.kind !== "confirm"}
            helperText={dialog?.kind === "confirm" ? "Optional" : "Required"}
          />
        </DialogContent>
        <DialogActions>
          <Button onClick={() => setDialog(null)}>Cancel</Button>
          <Button
            variant="contained"
            onClick={submitDialog}
            disabled={
              busy || (dialog?.kind !== "confirm" && !rationale.trim())
            }
          >
            {busy ? "Applying…" : "Apply"}
          </Button>
        </DialogActions>
      </Dialog>
    </Stack>
  );
}

function AlertList({ patientId, lastEvent }) {
  const [alerts, setAlerts] = useState([]);
  useEffect(() => {
    let cancelled = false;
    (async () => {
      try {
        const data = await api.alerts({ patient_id: patientId, limit: 50 });
        if (!cancelled) setAlerts(data.alerts ?? []);
      } catch {
        /* keep last */
      }
    })();
    return () => {
      cancelled = true;
    };
  }, [patientId, lastEvent]);

  if (!alerts.length)
    return (
      <Typography variant="body2" color="text.secondary">
        No alerts in the current window.
      </Typography>
    );

  return (
    <List>
      {alerts.map((a) => {
        let explanation = {};
        try {
          explanation = typeof a.explanation === "string" ? JSON.parse(a.explanation) : a.explanation ?? {};
        } catch {
          explanation = {};
        }
        const evidence = Array.isArray(explanation.evidence) ? explanation.evidence : [];
        const trend = explanation.trend ?? null;
        return (
          <ListItem key={a.id} divider alignItems="flex-start" sx={{ display: "block", py: 1.5 }}>
            <Stack direction="row" spacing={1} alignItems="center" flexWrap="wrap" gap={0.5} sx={{ mb: 0.5 }}>
              <Typography variant="body2" fontWeight={700} textTransform="capitalize">
                {String(a.trigger_type).replaceAll("_", " ")}
              </Typography>
              <SeverityChip severity={a.severity} />
              <StatusChip status={a.status} />
              <Chip size="small" variant="outlined" label={a.triggering_vital} />
              <Typography variant="caption" color="text.secondary">
                first {new Date(a.first_seen).toLocaleTimeString()} · last{" "}
                {new Date(a.last_seen).toLocaleTimeString()}
              </Typography>
            </Stack>
            {explanation.summary && (
              <Typography variant="body2" color="text.secondary" sx={{ mb: 0.5 }}>
                {explanation.summary}
              </Typography>
            )}
            {trend && (
              <Typography variant="caption" color="text.secondary" display="block">
                {trend.reading_count} readings · net {trend.net_delta} {trend.unit} over ~
                {Math.round(trend.span_minutes)} min
                {trend.consecutive_worsening ? " · consecutive worsening" : ""}
                {trend.abrupt_change ? " · abrupt change" : ""}
              </Typography>
            )}
            {evidence.length > 0 && (
              <Box component="ul" sx={{ mt: 0.5, mb: 0, pl: 2.5 }}>
                {evidence.slice(0, 6).map((e, i) => (
                  <li key={i}>
                    <Typography variant="caption" color="text.secondary">
                      {e.vital_type ?? e.vital}: {e.value}
                      {e.unit ? ` ${e.unit}` : ""}
                      {e.device_ts ? ` @ ${new Date(e.device_ts).toLocaleTimeString()}` : ""}
                    </Typography>
                  </li>
                ))}
              </Box>
            )}
            {explanation.missing_vitals?.length > 0 && (
              <Typography variant="caption" color="warning.main" display="block" sx={{ mt: 0.5 }}>
                Missing vitals: {explanation.missing_vitals.join(", ")}
              </Typography>
            )}
            {explanation.low_confidence && (
              <Typography variant="caption" color="warning.main" display="block">
                Low confidence (limited history)
              </Typography>
            )}
          </ListItem>
        );
      })}
    </List>
  );
}
