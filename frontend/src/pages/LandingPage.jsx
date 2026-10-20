import { Link as RouterLink } from "react-router-dom";
import {
  Box,
  Button,
  Container,
  Divider,
  Grid,
  Stack,
  Typography,
  useTheme,
} from "@mui/material";
import MonitorHeartIcon from "@mui/icons-material/MonitorHeart";
import TimelineIcon from "@mui/icons-material/Timeline";
import NotificationsActiveIcon from "@mui/icons-material/NotificationsActive";
import FactCheckIcon from "@mui/icons-material/FactCheck";
import BalanceIcon from "@mui/icons-material/Balance";
import VisibilityIcon from "@mui/icons-material/Visibility";
import RadarIcon from "@mui/icons-material/Radar";
import VerifiedUserIcon from "@mui/icons-material/VerifiedUser";
import BoltIcon from "@mui/icons-material/Bolt";
import BiotechIcon from "@mui/icons-material/Biotech";
import HealthAndSafetyIcon from "@mui/icons-material/HealthAndSafety";
import ArrowForwardIcon from "@mui/icons-material/ArrowForward";
import { RiskChip, TriageChip } from "../components/chips";
import { riskColors } from "../theme";

/* ---------- shared bits ---------- */

function Logo({ size = 34 }) {
  return (
    <Box
      sx={{
        width: size,
        height: size,
        borderRadius: 2.2,
        background: "linear-gradient(135deg,#2563eb 0%,#4f46e5 60%,#7c3aed 100%)",
        display: "grid",
        placeItems: "center",
        color: "white",
        boxShadow: "0 6px 16px rgba(37,99,235,0.35)",
        flexShrink: 0,
      }}
    >
      <HealthAndSafetyIcon sx={{ fontSize: size * 0.6 }} />
    </Box>
  );
}

function SectionTag({ children }) {
  return (
    <Box
      component="span"
      sx={{
        display: "inline-flex",
        alignItems: "center",
        gap: 1,
        px: 1.5,
        py: 0.5,
        borderRadius: "999px",
        border: "1px solid",
        borderColor: "primary.main",
        color: "primary.main",
        bgcolor: "rgba(37,99,235,0.06)",
        fontSize: 12,
        fontWeight: 750,
        letterSpacing: "0.08em",
        textTransform: "uppercase",
      }}
    >
      {children}
    </Box>
  );
}

const FEATURES = [
  {
    icon: <MonitorHeartIcon fontSize="inherit" />,
    title: "Four-vital continuous watch",
    body: "Heart rate, SpO₂, blood pressure and temperature from a rolling 4-hour window — the full signal an ED waiting room actually produces.",
  },
  {
    icon: <RadarIcon fontSize="inherit" />,
    title: "Deterioration risk scoring",
    body: "A gradient-boosted model scores every patient on each new reading. Bands stay honest: low history means abstain, never \u201csafe.\u201d",
  },
  {
    icon: <TimelineIcon fontSize="inherit" />,
    title: "Adverse-trend detection",
    body: "Independent of the model, rule-based trend logic catches abrupt single-reading drops and sustained declines within minutes.",
  },
  {
    icon: <NotificationsActiveIcon fontSize="inherit" />,
    title: "Deduplicated clinical alerts",
    body: "Alerts fire once per trigger with cooldown and material-worsening bypass — signal without alarm fatigue.",
  },
  {
    icon: <BalanceIcon fontSize="inherit" />,
    title: "Human-in-the-loop triage",
    body: "ESI recommendations are pending until a clinician confirms, rejects or overrides — each decision audited with rationale.",
  },
  {
    icon: <VisibilityIcon fontSize="inherit" />,
    title: "Structured explanations",
    body: "Every score ships with contributing readings, trend statistics, missing-vital flags and the exact model version. No black box.",
  },
];

const STEPS = [
  {
    n: "01",
    title: "Vitals stream in",
    body: "Observations arrive from monitors or replayed from real public-dataset exports. Validation rejects ambiguous units and impossible values.",
  },
  {
    n: "02",
    title: "Risk is computed live",
    body: "Each reading triggers window-based feature extraction, model inference, trend analysis and alert evaluation in one transaction.",
  },
  {
    n: "03",
    title: "Clinicians decide",
    body: "The dashboard surfaces risk bands, alerts and explainable ESI-move recommendations. Confirm, reject or override — always with rationale.",
  },
  {
    n: "04",
    title: "Everything is audited",
    body: "Append-only audit logs capture every decision and pipeline event. Failure of the audit write rolls the action back.",
  },
];

/* ---------- hero preview mock ---------- */

const PREVIEW_ROWS = [
  { id: "ED-4471", triage: 3, band: "high", score: 0.91, note: "HR ↑ 42 bpm / 38 min", alert: "High-risk alert · open" },
  { id: "ED-4468", triage: 2, band: "elevated", score: 0.64, note: "SpO₂ 91% · trend −4", alert: "Recommendation · pending" },
  { id: "ED-4473", triage: 4, band: "watch", score: 0.31, note: "Temp rising 37.4 → 38.2", alert: null },
  { id: "ED-4470", triage: 5, band: "low", score: 0.08, note: "Stable window · 38 readings", alert: null },
];

function HeroPreview() {
  return (
    <Box
      className="mq-float"
      sx={{
        borderRadius: 4,
        border: "1px solid #e2e8f0",
        bgcolor: "background.paper",
        boxShadow:
          "0 32px 64px -12px rgba(15,23,42,0.22), 0 0 0 1px rgba(15,23,42,0.03)",
        overflow: "hidden",
      }}
    >
      <Stack
        direction="row"
        alignItems="center"
        spacing={1.25}
        sx={{ px: 2.5, py: 1.75, bgcolor: "#0f172a" }}
      >
        <Box sx={{ width: 9, height: 9, borderRadius: "50%", bgcolor: "#22c55e" }} />
        <Typography sx={{ color: "#94a3b8", fontSize: 12.5, fontWeight: 650, letterSpacing: "0.04em" }}>
          Live ED queue
        </Typography>
        <Box sx={{ flex: 1 }} />
        <Typography sx={{ color: "#64748b", fontSize: 11.5 }}>realtime · websocket</Typography>
      </Stack>
      <Box sx={{ p: 0.5 }}>
        {PREVIEW_ROWS.map((row, i) => (
          <Box
            key={row.id}
            className="mq-row-in"
            sx={{
              display: "flex",
              alignItems: "center",
              gap: 1.5,
              px: 2,
              py: 1.35,
              mx: 0.5,
              borderRadius: 2.5,
              animationDelay: `${0.55 + i * 0.12}s`,
              "&:hover": { bgcolor: "#f8fafc" },
              transition: "background-color 160ms ease",
            }}
          >
            <Box
              sx={{
                width: 40,
                height: 40,
                borderRadius: 2,
                bgcolor: `${riskColors[row.band]}14`,
                color: riskColors[row.band],
                display: "grid",
                placeItems: "center",
                fontWeight: 800,
                fontSize: 13,
              }}
            >
              {Math.round(row.score * 100)}
            </Box>
            <Box sx={{ minWidth: 0, flex: 1 }}>
              <Stack direction="row" spacing={1} alignItems="center">
                <Typography sx={{ fontWeight: 750, fontSize: 14 }}>{row.id}</Typography>
                <TriageChip category={row.triage} />
              </Stack>
              <Typography sx={{ color: "text.secondary", fontSize: 12.5, mt: 0.25 }} noWrap>
                {row.note}
              </Typography>
            </Box>
            <RiskChip band={row.band} score={row.score} />
          </Box>
        ))}
      </Box>
      <Divider />
      <Stack direction="row" spacing={2.5} sx={{ px: 2.5, py: 1.4, bgcolor: "#f8fafc" }}>
        {[
          ["Model AUROC", "0.80"],
          ["Inference", "< 5 ms"],
          ["Abstains safely", "yes"],
        ].map(([k, v]) => (
          <Stack key={k}>
            <Typography sx={{ fontSize: 11, color: "text.secondary", fontWeight: 650 }}>{k}</Typography>
            <Typography sx={{ fontSize: 14, fontWeight: 800 }}>{v}</Typography>
          </Stack>
        ))}
      </Stack>
    </Box>
  );
}

/* ---------- page ---------- */

export default function LandingPage() {
  const theme = useTheme();

  return (
    <Box sx={{ minHeight: "100vh", bgcolor: "#ffffff" }}>
      {/* nav */}
      <Box
        component="header"
        className="mq-blur"
        sx={{
          position: "sticky",
          top: 0,
          zIndex: 50,
          borderBottom: "1px solid rgba(226,232,240,0.8)",
        }}
      >
        <Container maxWidth="lg">
          <Stack direction="row" alignItems="center" spacing={2} sx={{ py: 1.75 }}>
            <Logo size={36} />
            <Typography sx={{ fontWeight: 800, fontSize: 19, letterSpacing: "-0.02em" }}>
              MediQueue
            </Typography>
            <Box sx={{ flex: 1 }} />
            <Stack
              component="nav"
              direction="row"
              spacing={3}
              sx={{ display: { xs: "none", md: "flex" }, mr: 1 }}
            >
              {["Features", "How it works", "Safety"].map((label) => (
                <Typography
                  key={label}
                  component="a"
                  href={`#${label.toLowerCase().replace(/\s/g, "-")}`}
                  sx={{
                    fontSize: 14.5,
                    fontWeight: 600,
                    color: "text.secondary",
                    textDecoration: "none",
                    cursor: "pointer",
                    transition: "color 150ms ease",
                    "&:hover": { color: "primary.main" },
                  }}
                >
                  {label}
                </Typography>
              ))}
            </Stack>
            <Button
              component={RouterLink}
              to="/login"
              variant="contained"
              size="small"
              endIcon={<ArrowForwardIcon sx={{ fontSize: 17 }} />}
              sx={{ px: 2.5, py: 0.9 }}
            >
              Sign in
            </Button>
          </Stack>
        </Container>
      </Box>

      {/* hero */}
      <Box
        sx={{
          position: "relative",
          overflow: "hidden",
          background:
            "radial-gradient(900px 480px at 85% -10%, rgba(79,70,229,0.10), transparent 60%)," +
            "radial-gradient(700px 420px at 8% 0%, rgba(37,99,235,0.09), transparent 55%)," +
            "#ffffff",
        }}
      >
        <Container maxWidth="lg">
          <Grid container spacing={6} sx={{ py: { xs: 7, md: 11 }, alignItems: "center" }}>
            <Grid size={{ xs: 12, md: 6.4 }} className="mq-rise">
              <SectionTag>
                <BoltIcon sx={{ fontSize: 14 }} /> AI decision support for emergency departments
              </SectionTag>
              <Typography
                variant="h2"
                sx={{
                  mt: 3,
                  fontSize: { xs: "2.4rem", md: "3.3rem" },
                  fontWeight: 850,
                  letterSpacing: "-0.04em",
                  lineHeight: 1.08,
                  color: "#0f172a",
                }}
              >
                Catch patient deterioration{" "}
                <Box
                  component="span"
                  sx={{
                    background: "linear-gradient(92deg,#2563eb,#4f46e5 55%,#7c3aed)",
                    WebkitBackgroundClip: "text",
                    WebkitTextFillColor: "transparent",
                  }}
                >
                  before the waiting room does
                </Box>
              </Typography>
              <Typography
                sx={{
                  mt: 3,
                  fontSize: { xs: 16.5, md: 18 },
                  lineHeight: 1.65,
                  color: "text.secondary",
                  maxWidth: 560,
                }}
              >
                MediQueue continuously scores ED patients from four core vitals over a rolling
                four-hour window, surfaces deduplicated alerts with structured explanations, and
                proposes bounded triage adjustments — always pending a clinician's decision.
              </Typography>
              <Stack direction="row" spacing={1.5} sx={{ mt: 4.5, flexWrap: "wrap", gap: 1 }}>
                <Button
                  component={RouterLink}
                  to="/login"
                  variant="contained"
                  size="large"
                  endIcon={<ArrowForwardIcon />}
                  sx={{ px: 3.5, py: 1.35, fontSize: 15.5 }}
                >
                  Open the dashboard
                </Button>
                <Button
                  component="a"
                  href="#how-it-works"
                  variant="outlined"
                  size="large"
                  sx={{ px: 3.5, py: 1.35, fontSize: 15.5, borderColor: "#cbd5e1", color: "text.secondary" }}
                >
                  See how it works
                </Button>
              </Stack>
              <Stack direction="row" spacing={3} sx={{ mt: 5, flexWrap: "wrap", gap: 1.5 }}>
                {[
                  [<VerifiedUserIcon key="v" sx={{ fontSize: 18 }} />, "Human-in-the-loop by design"],
                  [<VisibilityIcon key="e" sx={{ fontSize: 18 }} />, "Explainable, never a black box"],
                  [<BiotechIcon key="b" sx={{ fontSize: 18 }} />, "Trained on real clinical data"],
                ].map(([icon, text], i) => (
                  <Stack key={i} direction="row" alignItems="center" spacing={0.75}>
                    <Box sx={{ color: "primary.main", display: "grid", placeItems: "center" }}>{icon}</Box>
                    <Typography sx={{ fontSize: 13.5, fontWeight: 600, color: "text.secondary" }}>
                      {text}
                    </Typography>
                  </Stack>
                ))}
              </Stack>
            </Grid>
            <Grid size={{ xs: 12, md: 5.6 }}>
              <HeroPreview />
            </Grid>
          </Grid>
        </Container>
      </Box>

      {/* stats strip */}
      <Box sx={{ bgcolor: "#0f172a", color: "white" }}>
        <Container maxWidth="lg">
          <Grid container sx={{ py: 4.5 }} columnSpacing={2}>
            {[
              ["4", "core vitals, continuously"],
              ["4 h", "rolling observation window"],
              ["1 ESI step", "max automated recommendation"],
              ["100 %", "decisions audit-logged"],
            ].map(([big, small], i) => (
              <Grid key={i} size={{ xs: 6, md: 3 }} sx={{ textAlign: "center", py: 1.5 }}>
                <Typography sx={{ fontSize: { xs: 26, md: 32 }, fontWeight: 850, letterSpacing: "-0.03em" }}>
                  {big}
                </Typography>
                <Typography sx={{ color: "#94a3b8", fontSize: 13.5, fontWeight: 550 }}>{small}</Typography>
              </Grid>
            ))}
          </Grid>
        </Container>
      </Box>

      {/* features */}
      <Container maxWidth="lg" id="features">
        <Stack alignItems="center" sx={{ py: { xs: 8, md: 11 }, textAlign: "center" }}>
          <SectionTag>Features</SectionTag>
          <Typography
            variant="h3"
            sx={{ mt: 2.5, fontSize: { xs: "1.85rem", md: "2.4rem" }, fontWeight: 850, letterSpacing: "-0.035em", color: "#0f172a" }}
          >
            Everything a waiting-room watch needs — nothing it doesn't
          </Typography>
          <Typography sx={{ mt: 2, color: "text.secondary", fontSize: 16.5, maxWidth: 620, lineHeight: 1.65 }}>
            Purpose-built around the SDD: a narrow vital set, a fixed window, honest abstention,
            deduplicated alerts and clinician-gated actions.
          </Typography>
        </Stack>
        <Grid container spacing={2.5} sx={{ pb: { xs: 8, md: 12 } }}>
          {FEATURES.map((f, i) => (
            <Grid key={f.title} size={{ xs: 12, sm: 6, md: 4 }} className="mq-card-in" sx={{ animationDelay: `${i * 0.07}s` }}>
              <Box
                sx={{
                  height: "100%",
                  p: 3.25,
                  borderRadius: 3.5,
                  border: "1px solid #e8edf4",
                  bgcolor: "#fbfcfe",
                  transition: "border-color 180ms ease, box-shadow 180ms ease, transform 180ms ease",
                  "&:hover": {
                    borderColor: "rgba(37,99,235,0.35)",
                    boxShadow: "0 14px 34px -8px rgba(37,99,235,0.14)",
                    transform: "translateY(-3px)",
                  },
                }}
              >
                <Box
                  sx={{
                    width: 46,
                    height: 46,
                    borderRadius: 2.5,
                    bgcolor: "rgba(37,99,235,0.08)",
                    color: "primary.main",
                    display: "grid",
                    placeItems: "center",
                    fontSize: 24,
                    mb: 2.25,
                  }}
                >
                  {f.icon}
                </Box>
                <Typography sx={{ fontWeight: 800, fontSize: 16.5, letterSpacing: "-0.015em" }}>{f.title}</Typography>
                <Typography sx={{ mt: 1.15, color: "text.secondary", fontSize: 14.5, lineHeight: 1.6 }}>{f.body}</Typography>
              </Box>
            </Grid>
          ))}
        </Grid>
      </Container>

      {/* how it works */}
      <Box id="how-it-works" sx={{ bgcolor: "#f8fafc", borderTop: "1px solid #eef2f7", borderBottom: "1px solid #eef2f7" }}>
        <Container maxWidth="lg">
          <Stack alignItems="center" sx={{ py: { xs: 8, md: 11 }, textAlign: "center" }}>
            <SectionTag>How it works</SectionTag>
            <Typography
              variant="h3"
              sx={{ mt: 2.5, fontSize: { xs: "1.85rem", md: "2.4rem" }, fontWeight: 850, letterSpacing: "-0.035em", color: "#0f172a" }}
            >
              From raw vitals to an audited clinical decision
            </Typography>
          </Stack>
          <Grid container spacing={2.5} sx={{ pb: { xs: 8, md: 11 } }}>
            {STEPS.map((s, i) => (
              <Grid key={s.n} size={{ xs: 12, sm: 6, md: 3 }} className="mq-card-in" sx={{ animationDelay: `${i * 0.09}s` }}>
                <Box sx={{ position: "relative", height: "100%", pr: 1 }}>
                  <Typography
                    sx={{
                      fontSize: 44,
                      fontWeight: 850,
                      letterSpacing: "-0.05em",
                      lineHeight: 1,
                      color: "rgba(37,99,235,0.16)",
                      mb: 1.5,
                    }}
                  >
                    {s.n}
                  </Typography>
                  <Typography sx={{ fontWeight: 800, fontSize: 16.5, letterSpacing: "-0.015em" }}>{s.title}</Typography>
                  <Typography sx={{ mt: 1.1, color: "text.secondary", fontSize: 14.5, lineHeight: 1.6 }}>{s.body}</Typography>
                </Box>
              </Grid>
            ))}
          </Grid>
        </Container>
      </Box>

      {/* safety */}
      <Container maxWidth="lg" id="safety">
        <Grid container spacing={6} sx={{ py: { xs: 8, md: 11 }, alignItems: "center" }}>
          <Grid size={{ xs: 12, md: 5.5 }}>
            <SectionTag>Safety first</SectionTag>
            <Typography
              variant="h3"
              sx={{
                mt: 2.5,
                fontSize: { xs: "1.85rem", md: "2.35rem" },
                fontWeight: 850,
                letterSpacing: "-0.035em",
                lineHeight: 1.15,
                color: "#0f172a",
              }}
            >
              Decision support.{" "}
              <Box component="span" sx={{ color: "text.secondary", fontWeight: 750 }}>
                Never a decision-maker.
              </Box>
            </Typography>
            <Stack spacing={2.25} sx={{ mt: 3.5 }}>
              {[
                ["No silent scores", "With too little history the model abstains — the UI shows \u201cno score,\u201d never \u201csafe.\u201d"],
                ["Bounded recommendations", "A confirmed recommendation can move ESI by at most one step; larger moves require a clinician override with rationale."],
                ["Stale-score transparency", "If inference fails, the prior score is retained but visibly marked STALE — never refreshed silently."],
                ["Append-only audit", "Every alert, recommendation and decision lands in an audit trail that the application cannot edit or delete."],
              ].map(([title, body]) => (
                <Stack key={title} direction="row" spacing={1.75}>
                  <Box sx={{ mt: 0.35, color: "primary.main" }}>
                    <VerifiedUserIcon sx={{ fontSize: 20 }} />
                  </Box>
                  <Box>
                    <Typography sx={{ fontWeight: 750, fontSize: 15 }}>{title}</Typography>
                    <Typography sx={{ color: "text.secondary", fontSize: 14.5, lineHeight: 1.55, mt: 0.25 }}>{body}</Typography>
                  </Box>
                </Stack>
              ))}
            </Stack>
          </Grid>
          <Grid size={{ xs: 12, md: 6.5 }}>
            <Box
              sx={{
                borderRadius: 4,
                p: { xs: 3, md: 4.5 },
                background: "linear-gradient(150deg,#0f172a 0%,#1e3a8a 70%,#312e81 100%)",
                color: "white",
                boxShadow: "0 28px 56px -16px rgba(15,23,42,0.45)",
              }}
            >
              <Typography sx={{ fontSize: 13, fontWeight: 750, letterSpacing: "0.09em", textTransform: "uppercase", color: "#93c5fd" }}>
                Structured explanation · every score
              </Typography>
              <Typography sx={{ mt: 2.5, fontWeight: 800, fontSize: 19, letterSpacing: "-0.02em" }}>
                Risk band: HIGH · score 0.91
              </Typography>
              <Stack spacing={1.5} sx={{ mt: 3 }}>
                {[
                  ["Evidence", "HR 128 bpm (↑ 42 over 38 min) · SpO₂ 93% · latest 2 min ago"],
                  ["Trend rule", "Sustained rise: 86 → 128 bpm across 5 consecutive readings"],
                  ["Model", "deterioration-lightgbm · AUROC 0.80 on held-out test"],
                  ["Coverage", "4/4 vitals present · 41 readings in window · high confidence"],
                ].map(([k, v]) => (
                  <Box key={k} sx={{ bgcolor: "rgba(255,255,255,0.06)", border: "1px solid rgba(255,255,255,0.09)", borderRadius: 2.5, px: 2, py: 1.4 }}>
                    <Typography sx={{ fontSize: 11.5, fontWeight: 700, letterSpacing: "0.07em", textTransform: "uppercase", color: "#93c5fd" }}>{k}</Typography>
                    <Typography sx={{ fontSize: 14, mt: 0.35, color: "#e2e8f0", lineHeight: 1.5 }}>{v}</Typography>
                  </Box>
                ))}
              </Stack>
              <Typography sx={{ mt: 3, fontSize: 13, color: "#94a3b8", fontStyle: "italic" }}>
                Recommendation pending clinician confirmation — ESI 3 → 2 (one-step bound).
              </Typography>
            </Box>
          </Grid>
        </Grid>
      </Container>

      {/* CTA */}
      <Box sx={{ bgcolor: "#f8fafc", borderTop: "1px solid #eef2f7" }}>
        <Container maxWidth="md">
          <Stack alignItems="center" sx={{ py: { xs: 8, md: 10 }, textAlign: "center" }}>
            <Logo size={52} />
            <Typography
              variant="h3"
              sx={{ mt: 3, fontSize: { xs: "1.7rem", md: "2.15rem" }, fontWeight: 850, letterSpacing: "-0.035em", color: "#0f172a" }}
            >
              See MediQueue in action
            </Typography>
            <Typography sx={{ mt: 2, color: "text.secondary", fontSize: 16, maxWidth: 520, lineHeight: 1.65 }}>
              Sign in with a demo account to explore the live queue, alerts, explanations,
              audit trail and the replay simulator.
            </Typography>
            <Button
              component={RouterLink}
              to="/login"
              variant="contained"
              size="large"
              endIcon={<ArrowForwardIcon />}
              sx={{ mt: 4, px: 4, py: 1.35, fontSize: 15.5 }}
            >
              Sign in to the dashboard
            </Button>
            <Typography sx={{ mt: 2, fontSize: 13, color: "text.secondary" }}>
              clinician1 · admin · auditor1 — passwords in the README
            </Typography>
          </Stack>
        </Container>
      </Box>

      {/* footer */}
      <Box component="footer" sx={{ bgcolor: "#0f172a", color: "#94a3b8" }}>
        <Container maxWidth="lg">
          <Stack
            direction={{ xs: "column", md: "row" }}
            spacing={2}
            alignItems={{ xs: "flex-start", md: "center" }}
            sx={{ py: 4 }}
          >
            <Stack direction="row" alignItems="center" spacing={1.5}>
              <Logo size={28} />
              <Typography sx={{ color: "white", fontWeight: 800, fontSize: 15 }}>MediQueue</Typography>
            </Stack>
            <Box sx={{ flex: 1 }} />
            <Typography sx={{ fontSize: 13 }}>
              Prototype decision support — not a medical device. Not for clinical use.
            </Typography>
          </Stack>
          <Divider sx={{ borderColor: "rgba(148,163,184,0.18)" }} />
          <Typography sx={{ py: 2.5, fontSize: 12.5 }}>
            © {new Date().getFullYear()} MediQueue · Apache-2.0 · Emergency department early-warning & dynamic triage
          </Typography>
        </Container>
      </Box>
    </Box>
  );
}
