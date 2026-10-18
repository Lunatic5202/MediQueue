import { useEffect, useMemo, useState } from "react";
import {
  Alert,
  Box,
  Button,
  Card,
  InputAdornment,
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
import SearchIcon from "@mui/icons-material/Search";
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
  const [search, setSearch] = useState("");
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

  const filteredEvents = useMemo(() => {
    const query = search.trim().toLowerCase();
    if (!query) return events;
    return events.filter((event) =>
      [
        event.id,
        event.ts,
        event.actor,
        event.event_type,
        event.entity_type,
        event.entity_id,
        JSON.stringify(event.payload ?? {}),
      ].some((value) => String(value ?? "").toLowerCase().includes(query)),
    );
  }, [events, search]);

  function exportCsv() {
    const header = ["id", "ts", "actor", "event_type", "entity_type", "entity_id", "payload"];
    const rows = events.map((e) =>
      [e.id, e.ts, e.actor, e.event_type, e.entity_type, e.entity_id, JSON.stringify(e.payload ?? {})]
        .map((v) => `"${String(v ?? "").replaceAll('"', '""')}"`)
        .join(","),
    );
    const blob = new Blob([header.join(",") + "\n" + rows.join("\n")], { type: "text/csv;charset=utf-8;" });
    const url = URL.createObjectURL(blob);
    const a = document.createElement("a");
    a.href = url;
    a.download = `mediqueue-audit-${new Date().toISOString().slice(0, 19)}.csv`;
    a.click();
    URL.revokeObjectURL(url);
  }

  return (
    <Stack spacing={2.5}>
      <Stack
        direction={{ xs: "column", lg: "row" }}
        alignItems={{ xs: "stretch", lg: "center" }}
        spacing={1.5}
      >
        <Box sx={{ flex: 1, minWidth: 0 }}>
          <Typography variant="h5" sx={{ fontWeight: 750 }}>Audit trail</Typography>
          <Typography variant="body2" color="text.secondary">
            Search recorded system actions and export the loaded audit records.
          </Typography>
        </Box>
        <Stack direction={{ xs: "column", sm: "row" }} spacing={1.25}>
          <TextField
            size="small"
            select
            label="Event type"
            value={eventType}
            onChange={(e) => setEventType(e.target.value)}
            sx={{ minWidth: { xs: "100%", sm: 220 } }}
          >
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
              <MenuItem key={t} value={t}>{t.replaceAll("_", " ")}</MenuItem>
            ))}
          </TextField>
          <TextField
            size="small"
            select
            label="Rows to load"
            value={limit}
            onChange={(e) => setLimit(Number(e.target.value))}
            sx={{ minWidth: { xs: "100%", sm: 130 } }}
          >
            {[100, 200, 500, 1000].map((n) => (
              <MenuItem key={n} value={n}>{n} rows</MenuItem>
            ))}
          </TextField>
          <Button
            variant="outlined"
            startIcon={<DownloadIcon />}
            onClick={exportCsv}
            sx={{ whiteSpace: "nowrap" }}
          >
            Export CSV
          </Button>
        </Stack>
      </Stack>

      {error && <Alert severity="error">{error}</Alert>}

      <Stack direction={{ xs: "column", sm: "row" }} spacing={1.5}>
        <Card sx={{ p: 2, flex: 1 }}>
          <Typography variant="body2" color="text.secondary">Records loaded</Typography>
          <Typography variant="h4" sx={{ mt: 0.5, fontWeight: 750, fontVariantNumeric: "tabular-nums" }}>
            {events.length}
          </Typography>
        </Card>
        <Card sx={{ p: 2, flex: 1 }}>
          <Typography variant="body2" color="text.secondary">Visible after search</Typography>
          <Typography variant="h4" sx={{ mt: 0.5, fontWeight: 750, fontVariantNumeric: "tabular-nums" }}>
            {filteredEvents.length}
          </Typography>
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
            <Typography variant="h6">Recorded events</Typography>
            <Typography variant="caption" color="text.secondary">
              Search applies to the currently loaded records; CSV exports all loaded records.
            </Typography>
          </Box>
          <TextField
            size="small"
            value={search}
            onChange={(e) => setSearch(e.target.value)}
            placeholder="Search actor, event, entity, payload…"
            aria-label="Search audit events"
            sx={{ width: { xs: "100%", sm: 340 } }}
            InputProps={{
              startAdornment: (
                <InputAdornment position="start">
                  <SearchIcon fontSize="small" />
                </InputAdornment>
              ),
            }}
          />
        </Stack>
        <TableContainer sx={{ maxHeight: "calc(100vh - 300px)" }}>
          <Table size="small" stickyHeader sx={{ minWidth: 950 }}>
            <TableHead>
              <TableRow>
                <TableCell width={70}>ID</TableCell>
                <TableCell width={180}>Timestamp (UTC)</TableCell>
                <TableCell width={120}>Actor</TableCell>
                <TableCell width={220}>Event</TableCell>
                <TableCell width={140}>Entity</TableCell>
                <TableCell>Payload</TableCell>
              </TableRow>
            </TableHead>
            <TableBody>
              {filteredEvents.map((e) => (
                <TableRow key={e.id} hover>
                  <TableCell>{e.id}</TableCell>
                  <TableCell>
                    <Typography variant="body2" sx={{ fontFamily: "monospace", fontSize: 11.5, whiteSpace: "nowrap" }}>
                      {e.ts ? new Date(e.ts).toISOString().replace("T", " ").slice(0, 19) : "—"}
                    </Typography>
                  </TableCell>
                  <TableCell>{e.actor ?? "—"}</TableCell>
                  <TableCell>
                    <Typography
                      variant="body2"
                      sx={{ color: EVENT_COLORS[e.event_type] ?? "text.primary", fontWeight: 650, fontSize: 12 }}
                    >
                      {String(e.event_type ?? "unknown").replaceAll("_", " ")}
                    </Typography>
                  </TableCell>
                  <TableCell sx={{ whiteSpace: "nowrap" }}>
                    {e.entity_type ?? "—"}/{e.entity_id ?? "—"}
                  </TableCell>
                  <TableCell sx={{ maxWidth: 560 }}>
                    <Typography
                      variant="caption"
                      title={JSON.stringify(e.payload ?? {})}
                      sx={{
                        display: "block",
                        fontFamily: "monospace",
                        color: "text.secondary",
                        whiteSpace: "nowrap",
                        overflow: "hidden",
                        textOverflow: "ellipsis",
                        maxWidth: 560,
                      }}
                    >
                      {e.payload ? JSON.stringify(e.payload) : "—"}
                    </Typography>
                  </TableCell>
                </TableRow>
              ))}
              {filteredEvents.length === 0 && (
                <TableRow>
                  <TableCell colSpan={6} align="center" sx={{ py: 6 }}>
                    <Typography variant="subtitle2">
                      {events.length ? "No events match your search" : "No audit events found"}
                    </Typography>
                    <Typography variant="body2" color="text.secondary" sx={{ mt: 0.5 }}>
                      {events.length ? "Try a different event name, actor, or entity ID." : "Recorded actions will appear here."}
                    </Typography>
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
