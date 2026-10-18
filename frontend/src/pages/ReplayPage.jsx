import { useEffect, useState } from "react";
import {
  Alert,
  Box,
  Button,
  Card,
  LinearProgress,
  MenuItem,
  Stack,
  TextField,
  Typography,
} from "@mui/material";
import PlayArrowIcon from "@mui/icons-material/PlayArrow";
import StopIcon from "@mui/icons-material/Stop";
import { api } from "../api";

const PROFILES = ["mixed", "stable", "sepsis_like", "respiratory_decline"];

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

  return (
    <Stack spacing={2.5}>
      <Typography variant="h5">Replay simulator</Typography>
      <Alert severity="info">
        Synthetic patient timelines replayed through the SAME ingestion pipeline as live HL7-style feeds:
        validation, history window, feature computation, model inference, alerting, recommendations. Replay
        results demonstrate system behavior — they are not clinical evidence.
      </Alert>
      {error && <Alert severity="error">{error}</Alert>}
      <Card sx={{ p: 3 }}>
        <Stack spacing={2.5} maxWidth={520}>
          <Box>
            <Typography variant="h6">{running ? "Replay running" : "Replay stopped"}</Typography>
            {status && (
              <Typography variant="body2" color="text.secondary">
                {status.events_emitted ?? 0} events emitted
                {status.n_patients ? ` · ${status.n_patients} patients` : ""}
                {status.rate_per_min ? ` · ${status.rate_per_min}/min` : ""}
                {status.started_at ? ` · started ${new Date(status.started_at).toLocaleTimeString()}` : ""}
              </Typography>
            )}
          </Box>
          {running && <LinearProgress />}
          <Stack direction="row" spacing={2}>
            <TextField
              select
              label="Scenario"
              size="small"
              value={scenario}
              onChange={(e) => setScenario(e.target.value)}
              disabled={running}
              fullWidth
            >
              {PROFILES.map((p) => (
                <MenuItem key={p} value={p}>
                  {p}
                </MenuItem>
              ))}
            </TextField>
            <TextField
              label="Patients"
              size="small"
              type="number"
              value={patients}
              onChange={(e) => setPatients(Number(e.target.value))}
              disabled={running}
              inputProps={{ min: 1, max: 50 }}
              fullWidth
            />
            <TextField
              label="Events / min"
              size="small"
              type="number"
              value={rate}
              onChange={(e) => setRate(Number(e.target.value))}
              disabled={running}
              inputProps={{ min: 1, max: 120 }}
              fullWidth
            />
          </Stack>
          <Stack direction="row" spacing={1.5}>
            <Button
              variant="contained"
              startIcon={<PlayArrowIcon />}
              onClick={start}
              disabled={busy || running}
            >
              Start replay
            </Button>
            <Button
              variant="outlined"
              color="error"
              startIcon={<StopIcon />}
              onClick={stop}
              disabled={busy || !running}
            >
              Stop replay
            </Button>
          </Stack>
        </Stack>
      </Card>
    </Stack>
  );
}
