import { useEffect, useState } from "react";
import {
  Alert,
  Box,
  Button,
  Card,
  Chip,
  Divider,
  Grid,
  LinearProgress,
  MenuItem,
  Stack,
  TextField,
  Typography,
} from "@mui/material";
import PlayArrowIcon from "@mui/icons-material/PlayArrow";
import StopIcon from "@mui/icons-material/Stop";
import { api } from "../api";

const PROFILES = [
  { value: "mixed", label: "Mixed signals", description: "A mix of stable and changing observations." },
  { value: "stable", label: "Stable", description: "Mostly steady observations for baseline testing." },
  { value: "sepsis_like", label: "Sepsis-like pattern", description: "Synthetic deterioration-style signal pattern." },
  { value: "respiratory_decline", label: "Respiratory decline", description: "Synthetic respiratory deterioration-style pattern." },
];

export default function ReplayPage({ lastEvent, onAction }) {
  const [status, setStatus] = useState(null);
  const [error, setError] = useState(null);
  const [busy, setBusy] = useState(false);
  const [scenario, setScenario] = useState("mixed");
  const [patients, setPatients] = useState(6);
  const [rate, setRate] = useState(10);

  async function refresh() {
    try {
      setStatus(await api.replayStatus());
      setError(null);
    } catch (err) {
      setError(err.message);
    }
  }

  useEffect(() => {
    refresh();
  }, [lastEvent]);

  async function start() {
    setBusy(true);
    try {
      await api.replayStart({ scenario, n_patients: patients, rate_per_min: rate });
      setError(null);
      onAction?.();
      await refresh();
    } catch (err) {
      setError(err.message);
    } finally {
      setBusy(false);
    }
  }

  async function stop() {
    setBusy(true);
    try {
      await api.replayStop();
      setError(null);
      onAction?.();
      await refresh();
    } catch (err) {
      setError(err.message);
    } finally {
      setBusy(false);
    }
  }

  const running = status?.running ?? false;
  const selectedProfile = PROFILES.find((p) => p.value === scenario);

  return (
    <Stack spacing={2.5}>
      <Box>
        <Typography variant="h5" sx={{ fontWeight: 750 }}>Replay simulator</Typography>
        <Typography variant="body2" color="text.secondary">
          Exercise the ingestion and alert pipeline with controlled synthetic patient streams.
        </Typography>
      </Box>

      <Alert severity="info">
        Replay events pass through the same ingestion pipeline as live HL7-style feeds: validation, history
        window, feature computation, model inference, alerting and recommendations. These synthetic scenarios
        demonstrate software behavior, not clinical evidence.
      </Alert>

      {error && <Alert severity="error">{error}</Alert>}

      <Grid container spacing={1.5}>
        <Grid size={{ xs: 12, sm: 4 }}>
          <Card sx={{ p: 2, height: "100%" }}>
            <Typography variant="body2" color="text.secondary">Simulator status</Typography>
            <Stack direction="row" alignItems="center" spacing={1} sx={{ mt: 1 }}>
              <Box sx={{
                width: 9, height: 9, borderRadius: "50%",
                bgcolor: running ? "success.main" : "text.disabled",
              }} />
              <Typography variant="h6">{running ? "Running" : status ? "Stopped" : "Checking…"}</Typography>
            </Stack>
            <Typography variant="caption" color="text.secondary">
              {running ? "Synthetic events are being emitted." : "No replay currently running."}
            </Typography>
          </Card>
        </Grid>
        <Grid size={{ xs: 12, sm: 4 }}>
          <Card sx={{ p: 2, height: "100%" }}>
            <Typography variant="body2" color="text.secondary">Events emitted</Typography>
            <Typography variant="h4" sx={{ mt: 0.5, fontWeight: 750, fontVariantNumeric: "tabular-nums" }}>
              {status?.events_emitted ?? "—"}
            </Typography>
            <Typography variant="caption" color="text.secondary">Reported by the replay service</Typography>
          </Card>
        </Grid>
        <Grid size={{ xs: 12, sm: 4 }}>
          <Card sx={{ p: 2, height: "100%" }}>
            <Typography variant="body2" color="text.secondary">Active configuration</Typography>
            <Typography variant="h6" sx={{ mt: 0.5 }}>
              {status?.n_patients ?? patients} patients
            </Typography>
            <Typography variant="caption" color="text.secondary">
              {status?.rate_per_min ?? rate} events per minute
            </Typography>
          </Card>
        </Grid>
      </Grid>

      <Card sx={{ p: { xs: 2, sm: 3 } }}>
        <Stack spacing={2.5}>
          <Box>
            <Typography variant="h6">Configure replay</Typography>
            <Typography variant="body2" color="text.secondary">
              Choose a scenario and stream intensity. Settings are locked while replay is running.
            </Typography>
          </Box>
          <Divider />
          <Grid container spacing={2}>
            <Grid size={{ xs: 12, md: 6 }}>
              <TextField
                select
                label="Synthetic scenario"
                value={scenario}
                onChange={(e) => setScenario(e.target.value)}
                disabled={running || busy}
                fullWidth
              >
                {PROFILES.map((p) => (
                  <MenuItem key={p.value} value={p.value}>{p.label}</MenuItem>
                ))}
              </TextField>
              <Typography variant="caption" color="text.secondary" sx={{ display: "block", mt: 0.75 }}>
                {selectedProfile?.description}
              </Typography>
            </Grid>
            <Grid size={{ xs: 12, sm: 6, md: 3 }}>
              <TextField
                label="Patients"
                type="number"
                value={patients}
                onChange={(e) => setPatients(Math.max(1, Math.min(50, Number(e.target.value) || 1)))}
                disabled={running || busy}
                inputProps={{ min: 1, max: 50, step: 1 }}
                fullWidth
                helperText="Between 1 and 50"
              />
            </Grid>
            <Grid size={{ xs: 12, sm: 6, md: 3 }}>
              <TextField
                label="Events per minute"
                type="number"
                value={rate}
                onChange={(e) => setRate(Math.max(1, Math.min(120, Number(e.target.value) || 1)))}
                disabled={running || busy}
                inputProps={{ min: 1, max: 120, step: 1 }}
                fullWidth
                helperText="Between 1 and 120"
              />
            </Grid>
          </Grid>
          {running && <LinearProgress />}
          {status?.started_at && (
            <Typography variant="caption" color="text.secondary">
              Started {new Date(status.started_at).toLocaleString()}
            </Typography>
          )}
          <Stack direction={{ xs: "column", sm: "row" }} spacing={1.25}>
            <Button
              variant="contained"
              startIcon={<PlayArrowIcon />}
              onClick={start}
              disabled={busy || running}
              fullWidth
              sx={{ maxWidth: { sm: 190 } }}
            >
              {busy && !running ? "Starting…" : "Start replay"}
            </Button>
            <Button
              variant="outlined"
              color="error"
              startIcon={<StopIcon />}
              onClick={stop}
              disabled={busy || !running}
              fullWidth
              sx={{ maxWidth: { sm: 170 } }}
            >
              {busy && running ? "Stopping…" : "Stop replay"}
            </Button>
            {status && (
              <Chip
                variant="outlined"
                label={running ? "Stream active" : "Ready to run"}
                color={running ? "success" : "default"}
                sx={{ alignSelf: { xs: "flex-start", sm: "center" }, ml: { sm: "auto !important" } }}
              />
            )}
          </Stack>
        </Stack>
      </Card>
    </Stack>
  );
}
