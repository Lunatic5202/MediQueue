import { useState } from "react";
import { Link as RouterLink, useNavigate } from "react-router-dom";
import {
  Alert,
  Box,
  Button,
  Card,
  Stack,
  TextField,
  Typography,
} from "@mui/material";
import { useAuth } from "../auth";

const ACCENT = "#5E0ED7";

const DEMO = [
  ["clinician1", "clinician1-pass", "Clinician"],
  ["admin", "admin-pass", "Administrator"],
  ["auditor1", "auditor-pass", "Auditor"],
];

function LogoMark({ size = 44 }) {
  return (
    <Box
      sx={{
        width: size,
        height: size,
        borderRadius: "50%",
        border: `2px solid ${ACCENT}`,
        display: "grid",
        placeItems: "center",
      }}
    >
      <Box sx={{ width: size * 0.28, height: size * 0.28, borderRadius: "50%", bgcolor: ACCENT }} />
    </Box>
  );
}

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
      navigate("/queue");
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
        background: "#060607",
        p: 2,
      }}
    >
      <Stack alignItems="center" spacing={2.5}>
        <Button
          component={RouterLink}
          to="/"
          variant="text"
          sx={{
            color: "rgba(255,255,255,0.6)",
            fontWeight: 600,
            fontSize: 12,
            letterSpacing: "0.18em",
            textTransform: "uppercase",
            "&:hover": { color: "rgba(255,255,255,0.9)", bgcolor: "transparent" },
          }}
        >
          ← Back to home
        </Button>
        <Card
          sx={{
            width: 420,
            p: 4,
            borderRadius: 0,
            border: "1px solid rgba(0,0,0,0.1)",
            boxShadow: "0 24px 60px rgba(94,14,215,0.18)",
          }}
        >
          <Stack alignItems="center" spacing={1.5} sx={{ mb: 3 }}>
            <LogoMark />
            <Typography
              sx={{
                fontWeight: 700,
                fontSize: 18,
                letterSpacing: "0.22em",
                textTransform: "uppercase",
                color: "#000",
              }}
            >
              MediQueue
            </Typography>
            <Typography
              sx={{
                color: "rgba(0,0,0,0.5)",
                fontSize: 12.5,
                textAlign: "center",
                lineHeight: 1.6,
                letterSpacing: 0,
              }}
            >
              Emergency department deterioration monitoring.
              <br />
              Decision support only — clinicians decide.
            </Typography>
          </Stack>
          {error && (
            <Alert severity="error" sx={{ mb: 2, borderRadius: 0 }}>
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
              />
              <TextField
                label="Password"
                type="password"
                value={password}
                onChange={(e) => setPassword(e.target.value)}
                fullWidth
              />
              <Button
                type="submit"
                variant="contained"
                size="large"
                disabled={busy}
                fullWidth
                sx={{
                  borderRadius: 0,
                  py: 1.25,
                  fontSize: 13,
                  fontWeight: 700,
                  letterSpacing: "0.18em",
                  textTransform: "uppercase",
                }}
              >
                {busy ? "Signing in…" : "Sign in"}
              </Button>
            </Stack>
          </form>
          <Box
            sx={{
              mt: 3,
              p: 1.75,
              bgcolor: "#F4EFFC",
              borderRadius: 0,
              border: "1px solid rgba(94,14,215,0.12)",
            }}
          >
            <Typography
              variant="caption"
              sx={{
                display: "block",
                mb: 1,
                color: "rgba(0,0,0,0.45)",
                fontSize: 10,
                fontWeight: 700,
                letterSpacing: "0.14em",
                textTransform: "uppercase",
              }}
            >
              Demo accounts
            </Typography>
            {DEMO.map(([u, p, role]) => (
              <Stack key={u} direction="row" justifyContent="space-between" sx={{ fontSize: 12.5 }}>
                <Typography variant="caption" sx={{ fontFamily: "monospace", color: "rgba(0,0,0,0.7)" }}>
                  {u} / {p}
                </Typography>
                <Typography variant="caption" sx={{ color: "rgba(0,0,0,0.45)" }}>
                  {role}
                </Typography>
              </Stack>
            ))}
          </Box>
        </Card>
      </Stack>
    </Box>
  );
}
