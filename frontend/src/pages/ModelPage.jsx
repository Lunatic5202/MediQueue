import { useEffect, useState } from "react";
import {
  Alert,
  Box,
  Card,
  Chip,
  Divider,
  List,
  ListItem,
  ListItemText,
  Stack,
  Table,
  TableBody,
  TableCell,
  TableContainer,
  TableHead,
  TableRow,
  Typography,
} from "@mui/material";
import { api } from "../api";

export default function ModelPage() {
  const [health, setHealth] = useState(null);
  const [error, setError] = useState(null);

  useEffect(() => {
    let cancelled = false;
    (async () => {
      try {
        const h = await api.health();
        if (!cancelled) {
          setHealth(h);
          setError(null);
        }
      } catch (err) {
        if (!cancelled) setError(err.message);
      }
    })();
    return () => {
      cancelled = true;
    };
  }, []);

  return (
    <Stack spacing={2.5}>
      <Typography variant="h5">Model & system health</Typography>
      {error && <Alert severity="error">{error}</Alert>}
      <Card sx={{ p: 3 }}>
        <Typography variant="h6" gutterBottom>
          Service health
        </Typography>
        <Divider sx={{ mb: 1.5 }} />
        {health ? (
          <Stack direction="row" spacing={2} flexWrap="wrap" gap={1}>
            <Chip
              label={health.status === "ok" ? "healthy" : health.status}
              color={health.status === "ok" ? "success" : "error"}
            />
            <Chip variant="outlined" label={`version ${health.version}`} />
            <Chip variant="outlined" label={`db: ${health.database}`} />
            <Chip variant="outlined" label={health.model_loaded ? "model loaded" : "NO MODEL"} color={health.model_loaded ? "success" : "error"} />
            <Chip variant="outlined" label={health.time ? new Date(health.time).toLocaleString() : ""} />
          </Stack>
        ) : (
          <LinearIndeterminate />
        )}
      </Card>

      <Alert severity="warning">
        <strong>Clinical disclaimer.</strong> MediQueue is a decision-support prototype. Risk scores,
        recommendations, and queue priorities are operational signals for clinician review — they are not
        diagnoses, are not prospectively validated, and must never be used as the sole basis for clinical
        decisions. Clinicians can reject or override every recommendation; every action is audited.
      </Alert>

      <Card sx={{ p: 3 }}>
        <Typography variant="h6" gutterBottom>
          How scoring works
        </Typography>
        <Divider sx={{ mb: 1.5 }} />
        <List dense>
          <ListItem>
            <ListItemText
              primary="1 · Rolling 4-hour window"
              secondary="Every accepted observation updates the patient's trailing 4h history of the 4 monitored vitals: heart rate, SpO₂, blood pressure, temperature."
            />
          </ListItem>
          <ListItem>
            <ListItemText
              primary="2 · Low-history rule"
              secondary="Fewer than 3 readings spanning under 10 minutes → the model abstains. Score is withheld (null), never displayed as 'safe'."
            />
          </ListItem>
          <ListItem>
            <ListItemText
              primary="3 · Feature computation & inference"
              secondary="Per-vital latest/mean/std/slope/delta features computed with the same code used offline for training. A versioned LightGBM model returns a calibrated deterioration score in [0,1]."
            />
          </ListItem>
          <ListItem>
            <ListItemText
              primary="4 · Fail-safe"
              secondary="If inference fails, no new score is written; the prior score is retained but flagged stale. Audit-write failure rolls back the entire action."
            />
          </ListItem>
          <ListItem>
            <ListItemText
              primary="5 · Alerts & recommendations"
              secondary="Absolute threshold + adverse-trend rules produce deduplicated alerts with structured (non-LLM) explanations. Recommendations require clinician confirmation; overrides require rationale."
            />
          </ListItem>
        </List>
      </Card>

      <Card sx={{ p: 3 }}>
        <Typography variant="h6" gutterBottom>
          Risk bands
        </Typography>
        <Divider sx={{ mb: 1.5 }} />
        <TableContainer>
          <Table size="small">
            <TableHead>
              <TableRow>
                <TableCell>Band</TableCell>
                <TableCell>Meaning</TableCell>
                <TableCell>Queue effect</TableCell>
              </TableRow>
            </TableHead>
            <TableBody>
              <TableRow>
                <TableCell>
                  <Chip size="small" sx={{ bgcolor: "#0596691a", color: "#059669" }} label="Low" />
                </TableCell>
                <TableCell>Below watch threshold</TableCell>
                <TableCell>None automatic</TableCell>
              </TableRow>
              <TableRow>
                <TableCell>
                  <Chip size="small" sx={{ bgcolor: "#0891b21a", color: "#0891b2" }} label="Watch" />
                </TableCell>
                <TableCell>Early signal</TableCell>
                <TableCell>Trend alert visible; recommendation if configured</TableCell>
              </TableRow>
              <TableRow>
                <TableCell>
                  <Chip size="small" sx={{ bgcolor: "#d977061a", color: "#d97706" }} label="Elevated" />
                </TableCell>
                <TableCell>Elevated deterioration risk</TableCell>
                <TableCell>Pending recommendation (ESI −1 step)</TableCell>
              </TableRow>
              <TableRow>
                <TableCell>
                  <Chip size="small" sx={{ bgcolor: "#dc26261a", color: "#dc2626" }} label="High" />
                </TableCell>
                <TableCell>High deterioration risk</TableCell>
                <TableCell>Priority alert + pending recommendation</TableCell>
              </TableRow>
            </TableBody>
          </Table>
        </TableContainer>
      </Card>
    </Stack>
  );
}

function LinearIndeterminate() {
  return (
    <Box sx={{ color: "text.secondary", fontSize: 13 }}>Loading…</Box>
  );
}
