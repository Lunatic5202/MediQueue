import { useEffect, useState } from "react";
import {
  Alert,
  Box,
  Card,
  Chip,
  Divider,
  Grid,
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

  const serviceHealthy = health?.status === "ok";
  const databaseHealthy = String(health?.database ?? "").toLowerCase() === "ok";
  const modelLoaded = Boolean(health?.model_loaded);

  return (
    <Stack spacing={2.5}>
      <Box>
        <Typography variant="h5" sx={{ fontWeight: 750 }}>Model & system health</Typography>
        <Typography variant="body2" color="text.secondary">
          Service readiness, model availability and the safeguards behind MediQueue's risk signals.
        </Typography>
      </Box>

      {error && <Alert severity="error">{error}</Alert>}

      <Card sx={{ p: { xs: 2, sm: 3 } }}>
        <Stack
          direction={{ xs: "column", sm: "row" }}
          alignItems={{ xs: "stretch", sm: "center" }}
          justifyContent="space-between"
          spacing={1.5}
          sx={{ mb: 2 }}
        >
          <Box>
            <Typography variant="h6">Service health</Typography>
            <Typography variant="body2" color="text.secondary">
              Latest response from the health endpoint
            </Typography>
          </Box>
          {health && (
            <Chip
              label={serviceHealthy ? "Service healthy" : `Service: ${health.status ?? "unknown"}`}
              color={serviceHealthy ? "success" : "error"}
              variant={serviceHealthy ? "filled" : "outlined"}
            />
          )}
        </Stack>
        <Divider sx={{ mb: 2 }} />
        {health ? (
          <Grid container spacing={1.5}>
            <Grid size={{ xs: 12, sm: 6, md: 3 }}>
              <HealthMetric label="API version" value={health.version ?? "—"} />
            </Grid>
            <Grid size={{ xs: 12, sm: 6, md: 3 }}>
              <HealthMetric label="Database" value={health.database ?? "Unknown"} good={databaseHealthy} />
            </Grid>
            <Grid size={{ xs: 12, sm: 6, md: 3 }}>
              <HealthMetric label="Model availability" value={modelLoaded ? "Loaded" : "Not loaded"} good={modelLoaded} />
            </Grid>
            <Grid size={{ xs: 12, sm: 6, md: 3 }}>
              <HealthMetric
                label="Last checked"
                value={health.time ? new Date(health.time).toLocaleString() : "Not reported"}
              />
            </Grid>
          </Grid>
        ) : (
          <Box sx={{ py: 2 }}>
            <Typography variant="body2" color="text.secondary">
              {error ? "Health information could not be loaded." : "Checking service health…"}
            </Typography>
          </Box>
        )}
      </Card>

      <Alert severity="warning">
        <strong>Clinical disclaimer.</strong> MediQueue is a decision-support prototype. Risk scores,
        recommendations and queue priorities are operational signals for clinician review—not diagnoses.
        They are not prospectively validated and must never be used as the sole basis for clinical decisions.
        Clinicians can reject or override recommendations, and actions are audited.
      </Alert>

      <Card sx={{ p: { xs: 2, sm: 3 } }}>
        <Typography variant="h6">How scoring works</Typography>
        <Typography variant="body2" color="text.secondary" sx={{ mt: 0.5 }}>
          The current pipeline uses recent observations and explicit safeguards before surfacing a score.
        </Typography>
        <Divider sx={{ my: 2 }} />
        <List disablePadding>
          <Step
            number="01"
            title="Rolling four-hour window"
            description="Accepted observations update the patient's trailing history for heart rate, SpO₂, blood pressure and temperature."
          />
          <Step
            number="02"
            title="Insufficient-history safeguard"
            description="Fewer than three readings spanning at least ten minutes causes the model to abstain. A missing score is not treated as a safe score."
          />
          <Step
            number="03"
            title="Features and inference"
            description="Per-vital latest, mean, standard deviation, slope and delta features feed the versioned LightGBM model, which returns a deterioration score between 0 and 1."
          />
          <Step
            number="04"
            title="Fail-safe behavior"
            description="If inference fails, the previous score is retained and marked stale. Audit-write failure rolls back the action."
          />
          <Step
            number="05"
            title="Alerts and clinician decisions"
            description="Threshold and adverse-trend rules generate structured explanations. Recommendations require clinician review; overrides require a rationale."
            last
          />
        </List>
      </Card>

      <Card sx={{ p: { xs: 2, sm: 3 } }}>
        <Typography variant="h6">Risk bands</Typography>
        <Typography variant="body2" color="text.secondary" sx={{ mt: 0.5 }}>
          Application-defined categories; they should not be interpreted as validated clinical thresholds.
        </Typography>
        <Divider sx={{ my: 2 }} />
        <TableContainer>
          <Table size="small" sx={{ minWidth: 520 }}>
            <TableHead>
              <TableRow>
                <TableCell>Band</TableCell>
                <TableCell>Meaning</TableCell>
                <TableCell>Queue behavior</TableCell>
              </TableRow>
            </TableHead>
            <TableBody>
              <TableRow>
                <TableCell><Band label="Low" color="#047857" /></TableCell>
                <TableCell>Below watch threshold</TableCell>
                <TableCell>No automatic change</TableCell>
              </TableRow>
              <TableRow>
                <TableCell><Band label="Watch" color="#0e7490" /></TableCell>
                <TableCell>Early signal</TableCell>
                <TableCell>Trend alert; recommendation if configured</TableCell>
              </TableRow>
              <TableRow>
                <TableCell><Band label="Elevated" color="#b45309" /></TableCell>
                <TableCell>Elevated deterioration signal</TableCell>
                <TableCell>Pending one-step recommendation</TableCell>
              </TableRow>
              <TableRow>
                <TableCell><Band label="High" color="#b91c1c" /></TableCell>
                <TableCell>High deterioration signal</TableCell>
                <TableCell>Priority alert and pending recommendation</TableCell>
              </TableRow>
            </TableBody>
          </Table>
        </TableContainer>
      </Card>
    </Stack>
  );
}

function HealthMetric({ label, value, good }) {
  return (
    <Box sx={{ p: 1.5, height: "100%", border: 1, borderColor: "divider", borderRadius: 2, minWidth: 0 }}>
      <Typography variant="caption" color="text.secondary">{label}</Typography>
      <Stack direction="row" alignItems="center" spacing={0.75} sx={{ mt: 0.5 }}>
        {good !== undefined && (
          <Box sx={{ width: 7, height: 7, borderRadius: "50%", bgcolor: good ? "success.main" : "error.main", flexShrink: 0 }} />
        )}
        <Typography variant="subtitle2" sx={{ overflowWrap: "anywhere" }}>{value}</Typography>
      </Stack>
    </Box>
  );
}

function Step({ number, title, description, last = false }) {
  return (
    <ListItem
      alignItems="flex-start"
      sx={{ px: 0, py: 1.5, borderBottom: last ? 0 : 1, borderColor: "divider", gap: 1.5 }}
    >
      <Box sx={{
        minWidth: 38, height: 38, borderRadius: 2, display: "grid", placeItems: "center",
        bgcolor: "primary.main", color: "primary.contrastText", fontWeight: 750, fontSize: 12,
      }}>
        {number}
      </Box>
      <ListItemText
        primary={<Typography variant="subtitle2">{title}</Typography>}
        secondary={<Typography variant="body2" color="text.secondary" sx={{ mt: 0.35 }}>{description}</Typography>}
      />
    </ListItem>
  );
}

function Band({ label, color }) {
  return <Chip size="small" sx={{ bgcolor: `${color}1a`, color, fontWeight: 700 }} label={label} />;
}
