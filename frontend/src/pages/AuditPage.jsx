import { useEffect, useState } from "react";
import {
  Alert,
  Button,
  Card,
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
import DownloadIcon from "@mui/icons-material/Download";
import { api } from "../api";

const EVENT_COLORS = {
  recommendation_confirmed: "#059669",
  recommendation_rejected: "#64748b",
  recommendation_overridden: "#7c3aed",
  queue_event: "#2563eb",
  alert_created: "#dc2626",
  risk_score_computed: "#0891b2",
};

export default function AuditPage() {
  const [events, setEvents] = useState([]);
  const [limit, setLimit] = useState(200);
  const [eventType, setEventType] = useState("");
  const [error, setError] = useState(null);

  useEffect(() => {
    let cancelled = false;
    (async () => {
      try {
        const params = { limit };
        if (eventType) params.event_type = eventType;
        const data = await api.audit(params);
        if (!cancelled) {
          setEvents(data.events ?? []);
          setError(null);
        }
      } catch (err) {
        if (!cancelled) setError(err.message);
      }
    })();
    return () => {
      cancelled = true;
    };
  }, [limit, eventType]);

  function exportCsv() {
    const header = ["id", "ts", "actor", "event_type", "entity_type", "entity_id", "payload"];
    const rows = events.map((e) =>
      [e.id, e.ts, e.actor, e.event_type, e.entity_type, e.entity_id, JSON.stringify(e.payload ?? {})]
        .map((v) => `"${String(v ?? "").replaceAll('"', '""')}"`)
        .join(","),
    );
    const blob = new Blob([header.join(",") + "\n" + rows.join("\n")], { type: "text/csv" });
    const url = URL.createObjectURL(blob);
    const a = document.createElement("a");
    a.href = url;
    a.download = `mediqueue-audit-${new Date().toISOString().slice(0, 19)}.csv`;
    a.click();
    URL.revokeObjectURL(url);
  }

  return (
    <Stack spacing={2.5}>
      <Stack direction="row" alignItems="center" spacing={2}>
        <Typography variant="h5" sx={{ flex: 1 }}>
          Audit trail
        </Typography>
        <TextField size="small" select value={eventType} onChange={(e) => setEventType(e.target.value)} sx={{ width: 240 }}>
          <MenuItem value="">All event types</MenuItem>
          {[
            "patient_registered",
            "observation_duplicate",
            "late_observation",
            "risk_score_computed",
            "inference_abstained",
            "inference_failed",
            "score_marked_stale",
            "alert_created",
            "alert_updated",
            "recommendation_created",
            "recommendation_confirmed",
            "recommendation_rejected",
            "recommendation_overridden",
            "queue_event",
          ].map((t) => (
            <MenuItem key={t} value={t}>
              {t}
            </MenuItem>
          ))}
        </TextField>
        <TextField
          size="small"
          select
          value={limit}
          onChange={(e) => setLimit(Number(e.target.value))}
          sx={{ width: 120 }}
        >
          {[100, 200, 500, 1000].map((n) => (
            <MenuItem key={n} value={n}>
              {n} rows
            </MenuItem>
          ))}
        </TextField>
        <Button variant="outlined" startIcon={<DownloadIcon />} onClick={exportCsv}>
          Export CSV
        </Button>
      </Stack>
      {error && <Alert severity="error">{error}</Alert>}
      <Card>
        <TableContainer sx={{ maxHeight: "calc(100vh - 220px)" }}>
          <Table size="small" stickyHeader>
            <TableHead>
              <TableRow>
                <TableCell width={70}>ID</TableCell>
                <TableCell width={180}>Timestamp (UTC)</TableCell>
                <TableCell width={120}>Actor</TableCell>
                <TableCell width={220}>Event</TableCell>
                <TableCell width={110}>Entity</TableCell>
                <TableCell>Payload</TableCell>
              </TableRow>
            </TableHead>
            <TableBody>
              {events.map((e) => (
                <TableRow key={e.id} hover>
                  <TableCell>{e.id}</TableCell>
                  <TableCell>
                    <Typography variant="body2" sx={{ fontFamily: "monospace", fontSize: 11.5 }}>
                      {e.ts ? new Date(e.ts).toISOString().replace("T", " ").slice(0, 19) : "—"}
                    </Typography>
                  </TableCell>
                  <TableCell>{e.actor}</TableCell>
                  <TableCell>
                    <Typography
                      variant="body2"
                      sx={{ color: EVENT_COLORS[e.event_type] ?? "text.primary", fontWeight: 600, fontSize: 12 }}
                    >
                      {e.event_type}
                    </Typography>
                  </TableCell>
                  <TableCell>
                    {e.entity_type}/{e.entity_id}
                  </TableCell>
                  <TableCell>
                    <Typography
                      variant="caption"
                      sx={{ fontFamily: "monospace", color: "text.secondary", wordBreak: "break-all" }}
                    >
                      {e.payload ? JSON.stringify(e.payload) : ""}
                    </Typography>
                  </TableCell>
                </TableRow>
              ))}
              {events.length === 0 && (
                <TableRow>
                  <TableCell colSpan={6} align="center" sx={{ py: 4, color: "text.secondary" }}>
                    No audit events match.
                  </TableCell>
                </TableRow>
              )}
            </TableBody>
          </Table>
        </TableContainer>
      </Card>
      <Alert severity="info">
        The audit log is append-only (enforced by database triggers). Risk-scoring actions persist the audit
        write in the same transaction as the action — if audit persistence fails, the action is rolled back
        and reported as a failure.
      </Alert>
    </Stack>
  );
}
