import { useEffect, useMemo, useState } from "react";
import { Link as RouterLink } from "react-router-dom";
import {
  Alert as MuiAlert,
  Box,
  Card,
  Chip,
  InputAdornment,
  Link,
  MenuItem,
  Stack,
  Table,
  TableBody,
  TableCell,
  TableContainer,
  TableHead,
  TableRow,
  TextField,
  Typography,
} from "@mui/material";
import SearchIcon from "@mui/icons-material/Search";
import { api } from "../api";
import { SeverityChip, StatusChip } from "../components/chips";

function getSummary(explanation) {
  try {
    const parsed = typeof explanation === "string" ? JSON.parse(explanation) : explanation ?? {};
    return parsed.summary ?? "";
  } catch {
    return "";
  }
}

export default function AlertsPage({ lastEvent }) {
  const [alerts, setAlerts] = useState([]);
  const [status, setStatus] = useState("open");
  const [search, setSearch] = useState("");
  const [error, setError] = useState(null);

  useEffect(() => {
    let cancelled = false;
    (async () => {
      try {
        const data = await api.alerts({ status, limit: 300 });
        if (!cancelled) {
          setAlerts(data.alerts ?? []);
          setError(null);
        }
      } catch (err) {
        if (!cancelled) setError(err.message);
      }
    })();
    return () => {
      cancelled = true;
    };
  }, [status, lastEvent]);

  const filteredAlerts = useMemo(() => {
    const query = search.trim().toLowerCase();
    if (!query) return alerts;
    return alerts.filter((alert) =>
      [
        alert.patient_id,
        alert.severity,
        alert.trigger_type,
        alert.triggering_vital,
        alert.status,
        getSummary(alert.explanation),
      ]
        .some((value) => String(value ?? "").toLowerCase().includes(query)),
    );
  }, [alerts, search]);

  const criticalCount = alerts.filter((a) =>
    ["critical", "high"].includes(String(a.severity ?? "").toLowerCase()),
  ).length;

  return (
    <Stack spacing={2.5}>
      <Stack
        direction={{ xs: "column", sm: "row" }}
        alignItems={{ xs: "stretch", sm: "center" }}
        spacing={1.5}
      >
        <Box sx={{ flex: 1, minWidth: 0 }}>
          <Typography variant="h5" sx={{ fontWeight: 750 }}>Alert center</Typography>
          <Typography variant="body2" color="text.secondary">
            Review patient deterioration signals and their supporting explanations.
          </Typography>
        </Box>
        <TextField
          size="small"
          select
          label="Alert status"
          value={status}
          onChange={(e) => setStatus(e.target.value)}
          sx={{ width: { xs: "100%", sm: 180 }, flexShrink: 0 }}
        >
          <MenuItem value="open">Open</MenuItem>
          <MenuItem value="suppressed">Suppressed</MenuItem>
          <MenuItem value="resolved">Resolved</MenuItem>
          <MenuItem value="all">All statuses</MenuItem>
        </TextField>
      </Stack>

      {error && <MuiAlert severity="error">{error}</MuiAlert>}

      <Stack direction={{ xs: "column", sm: "row" }} spacing={1.5}>
        <Card sx={{ p: 2, flex: 1 }}>
          <Typography variant="body2" color="text.secondary">Alerts loaded</Typography>
          <Typography variant="h4" sx={{ mt: 0.5, fontWeight: 750, fontVariantNumeric: "tabular-nums" }}>
            {alerts.length}
          </Typography>
          <Typography variant="caption" color="text.secondary">Current status selection</Typography>
        </Card>
        <Card sx={{ p: 2, flex: 1 }}>
          <Typography variant="body2" color="text.secondary">High-priority signals</Typography>
          <Typography variant="h4" sx={{ mt: 0.5, fontWeight: 750, fontVariantNumeric: "tabular-nums" }}>
            {criticalCount}
          </Typography>
          <Typography variant="caption" color="text.secondary">Critical or high severity</Typography>
        </Card>
        <Card sx={{ p: 2, flex: 1 }}>
          <Typography variant="body2" color="text.secondary">Matching results</Typography>
          <Typography variant="h4" sx={{ mt: 0.5, fontWeight: 750, fontVariantNumeric: "tabular-nums" }}>
            {filteredAlerts.length}
          </Typography>
          <Typography variant="caption" color="text.secondary">After search filtering</Typography>
        </Card>
      </Stack>

      <Card>
        <Stack
          direction={{ xs: "column", sm: "row" }}
          spacing={1.5}
          alignItems={{ xs: "stretch", sm: "center" }}
          sx={{ p: 2, borderBottom: 1, borderColor: "divider" }}
        >
          <Box sx={{ flex: 1 }}>
            <Typography variant="h6">Patient alerts</Typography>
            <Typography variant="caption" color="text.secondary">
              Select a patient to inspect their timeline and risk evidence.
            </Typography>
          </Box>
          <TextField
            size="small"
            value={search}
            onChange={(e) => setSearch(e.target.value)}
            placeholder="Search patient, vital, trigger…"
            aria-label="Search alerts"
            sx={{ width: { xs: "100%", sm: 300 } }}
            InputProps={{
              startAdornment: (
                <InputAdornment position="start">
                  <SearchIcon fontSize="small" />
                </InputAdornment>
              ),
            }}
          />
        </Stack>
        <TableContainer>
          <Table size="small" sx={{ minWidth: 900 }}>
            <TableHead>
              <TableRow>
                <TableCell>Severity</TableCell>
                <TableCell>Trigger</TableCell>
                <TableCell>Vital</TableCell>
                <TableCell>Patient</TableCell>
                <TableCell>Explanation summary</TableCell>
                <TableCell>Status</TableCell>
                <TableCell>First seen</TableCell>
                <TableCell>Last seen</TableCell>
              </TableRow>
            </TableHead>
            <TableBody>
              {filteredAlerts.map((a) => (
                <TableRow key={a.id} hover>
                  <TableCell><SeverityChip severity={a.severity} /></TableCell>
                  <TableCell>
                    <Typography variant="body2" textTransform="capitalize">
                      {String(a.trigger_type ?? "unknown").replaceAll("_", " ")}
                    </Typography>
                  </TableCell>
                  <TableCell>
                    <Chip size="small" variant="outlined" label={a.triggering_vital ?? "—"} />
                  </TableCell>
                  <TableCell>
                    <Link
                      component={RouterLink}
                      to={`/patients/${encodeURIComponent(a.patient_id)}`}
                      underline="hover"
                      fontWeight={700}
                    >
                      {a.patient_id}
                    </Link>
                  </TableCell>
                  <TableCell sx={{ maxWidth: 380 }}>
                    <Typography variant="body2" color="text.secondary" noWrap title={getSummary(a.explanation)}>
                      {getSummary(a.explanation) || "No explanation summary provided"}
                    </Typography>
                  </TableCell>
                  <TableCell><StatusChip status={a.status} /></TableCell>
                  <TableCell sx={{ whiteSpace: "nowrap" }}>
                    {a.first_seen ? new Date(a.first_seen).toLocaleTimeString() : "—"}
                  </TableCell>
                  <TableCell sx={{ whiteSpace: "nowrap" }}>
                    {a.last_seen ? new Date(a.last_seen).toLocaleTimeString() : "—"}
                  </TableCell>
                </TableRow>
              ))}
              {filteredAlerts.length === 0 && (
                <TableRow>
                  <TableCell colSpan={8} align="center" sx={{ py: 6 }}>
                    <Typography variant="subtitle2">
                      {alerts.length ? "No alerts match your search" : `No ${status} alerts`}
                    </Typography>
                    <Typography variant="body2" color="text.secondary" sx={{ mt: 0.5 }}>
                      {alerts.length ? "Try another patient ID, vital, or trigger." : "New signals will appear here as they are recorded."}
                    </Typography>
                  </TableCell>
                </TableRow>
              )}
            </TableBody>
          </Table>
        </TableContainer>
        <Box sx={{ px: 2, py: 1.5, borderTop: 1, borderColor: "divider" }}>
          <Typography variant="caption" color="text.secondary">
            Alerts are deduplicated per patient/trigger/vital with a 15-minute cooldown. Material worsening
            (score jump or band increase) bypasses suppression and opens a new alert.
          </Typography>
        </Box>
      </Card>
    </Stack>
  );
}
