import { useEffect, useState } from "react";
import { Link as RouterLink } from "react-router-dom";
import {
  Box,
  Card,
  Chip,
  Link,
  List,
  ListItem,
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
  Alert as MuiAlert,
} from "@mui/material";
import { api } from "../api";
import { SeverityChip, StatusChip } from "../components/chips";

export default function AlertsPage({ lastEvent }) {
  const [alerts, setAlerts] = useState([]);
  const [status, setStatus] = useState("open");
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

  return (
    <Stack spacing={2.5}>
      <Stack direction="row" alignItems="center" spacing={2}>
        <Typography variant="h5" sx={{ flex: 1 }}>
          Alerts
        </Typography>
        <TextField size="small" select value={status} onChange={(e) => setStatus(e.target.value)} sx={{ width: 180 }}>
          <MenuItem value="open">Open</MenuItem>
          <MenuItem value="suppressed">Suppressed</MenuItem>
          <MenuItem value="resolved">Resolved</MenuItem>
          <MenuItem value="all">All</MenuItem>
        </TextField>
      </Stack>
      {error && <MuiAlert severity="error">{error}</MuiAlert>}
      <Card>
        <TableContainer>
          <Table size="small">
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
              {alerts.map((a) => {
                let summary = "";
                try {
                  const e = typeof a.explanation === "string" ? JSON.parse(a.explanation) : a.explanation ?? {};
                  summary = e.summary ?? "";
                } catch {
                  summary = "";
                }
                return (
                  <TableRow key={a.id} hover>
                    <TableCell>
                      <SeverityChip severity={a.severity} />
                    </TableCell>
                    <TableCell>
                      <Typography variant="body2" textTransform="capitalize">
                        {String(a.trigger_type).replaceAll("_", " ")}
                      </Typography>
                    </TableCell>
                    <TableCell>
                      <Chip size="small" variant="outlined" label={a.triggering_vital} />
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
                      <Typography variant="body2" color="text.secondary" noWrap>
                        {summary}
                      </Typography>
                    </TableCell>
                    <TableCell>
                      <StatusChip status={a.status} />
                    </TableCell>
                    <TableCell>{new Date(a.first_seen).toLocaleTimeString()}</TableCell>
                    <TableCell>{new Date(a.last_seen).toLocaleTimeString()}</TableCell>
                  </TableRow>
                );
              })}
              {alerts.length === 0 && (
                <TableRow>
                  <TableCell colSpan={8} align="center" sx={{ py: 4, color: "text.secondary" }}>
                    No {status} alerts.
                  </TableCell>
                </TableRow>
              )}
            </TableBody>
          </Table>
        </TableContainer>
      </Card>
      <Box>
        <Typography variant="caption" color="text.secondary">
          Alerts are deduplicated per patient/trigger/vital with a 15-minute cooldown. Material worsening
          (score jump or band increase) bypasses suppression and opens a new alert.
        </Typography>
      </Box>
    </Stack>
  );
}
