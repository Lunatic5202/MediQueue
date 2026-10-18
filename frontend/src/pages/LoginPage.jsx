import { useState } from "react";
import { useNavigate } from "react-router-dom";
import {
  Alert,
  Box,
  Button,
  Card,
  IconButton,
  InputAdornment,
  Stack,
  TextField,
  Typography,
} from "@mui/material";
import PersonIcon from "@mui/icons-material/Person";
import LockIcon from "@mui/icons-material/Lock";
import HealthAndSafetyIcon from "@mui/icons-material/HealthAndSafety";
import { useAuth } from "../auth";

const DEMO = [
  ["clinician1", "clinician1-pass", "Clinician"],
  ["admin", "admin-pass", "Administrator"],
  ["auditor1", "auditor-pass", "Auditor"],
];

export default function LoginPage() {
  const { login } = useAuth();
  const navigate = useNavigate();
  const [username, setUsername] = useState("clinician1");
  const [password, setPassword] = useState("clinician1-pass");
  const [error, setError] = useState(null);
  const [busy, setBusy] = useState(false);

  async function submit(e) {
    e.preventDefault();
    setBusy(true);
    setError(null);
    try {
      await login(username.trim(), password);
      navigate("/");
    } catch (err) {
      setError(err.message || "Sign-in failed");
    } finally {
      setBusy(false);
    }
  }

  return (
    <Box
      sx={{
        minHeight: "100vh",
        display: "grid",
        placeItems: "center",
        background: "linear-gradient(135deg,#0f172a 0%,#1e3a8a 55%,#312e81 100%)",
        p: 2,
      }}
    >
      <Card sx={{ width: 420, p: 4, borderRadius: 4 }}>
        <Stack alignItems="center" spacing={1} sx={{ mb: 3 }}>
          <Box
            sx={{
              width: 56,
              height: 56,
              borderRadius: 3,
              background: "linear-gradient(135deg,#2563eb,#7c3aed)",
              display: "grid",
              placeItems: "center",
              color: "white",
            }}
          >
            <HealthAndSafetyIcon sx={{ fontSize: 30 }} />
          </Box>
          <Typography variant="h5">MediQueue</Typography>
          <Typography color="text.secondary" textAlign="center">
            Emergency department deterioration monitoring.
            <br />
            Decision support only — clinicians decide.
          </Typography>
        </Stack>
        {error && (
          <Alert severity="error" sx={{ mb: 2 }}>
            {error}
          </Alert>
        )}
        <form onSubmit={submit}>
          <Stack spacing={2}>
            <TextField
              label="Username"
              value={username}
              onChange={(e) => setUsername(e.target.value)}
              fullWidth
              slotProps={{
                input: {
                  startAdornment: (
                    <InputAdornment position="start">
                      <PersonIcon fontSize="small" />
                    </InputAdornment>
                  ),
                },
              }}
            />
            <TextField
              label="Password"
              type="password"
              value={password}
              onChange={(e) => setPassword(e.target.value)}
              fullWidth
              slotProps={{
                input: {
                  startAdornment: (
                    <InputAdornment position="start">
                      <LockIcon fontSize="small" />
                    </InputAdornment>
                  ),
                },
              }}
            />
            <Button type="submit" variant="contained" size="large" disabled={busy} fullWidth>
              {busy ? "Signing in…" : "Sign in"}
            </Button>
          </Stack>
        </form>
        <Box sx={{ mt: 3, p: 1.5, bgcolor: "#f8fafc", borderRadius: 2, border: "1px solid #e2e8f0" }}>
          <Typography variant="caption" color="text.secondary" display="block" gutterBottom>
            Demo accounts
          </Typography>
          {DEMO.map(([u, p, role]) => (
            <Stack key={u} direction="row" justifyContent="space-between" sx={{ fontSize: 12.5 }}>
              <Typography variant="caption" sx={{ fontFamily: "monospace" }}>
                {u} / {p}
              </Typography>
              <Typography variant="caption" color="text.secondary">
                {role}
              </Typography>
            </Stack>
          ))}
        </Box>
      </Card>
    </Box>
  );
}
