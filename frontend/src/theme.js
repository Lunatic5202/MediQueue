import { createTheme } from "@mui/material/styles";

const primary = { main: "#5E0ED7", dark: "#4A0BB0", light: "#8B4FE8" };
const success = { main: "#047857" };
const warning = { main: "#b45309" };
const error = { main: "#b91c1c" };
const info = { main: "#0e7490" };

export const riskColors = {
  low: "#047857",
  watch: "#0e7490",
  elevated: "#b45309",
  high: "#b91c1c",
  unknown: "#64748b",
};

export const theme = createTheme({
  palette: {
    mode: "light",
    primary,
    success,
    warning,
    error,
    info,
    background: { default: "#f5f7fb", paper: "#ffffff" },
    text: { primary: "#172033", secondary: "#667085" },
    divider: "#e6eaf0",
  },
  shape: { borderRadius: 14 },
  typography: {
    fontFamily: '"Inter", "Segoe UI", system-ui, -apple-system, sans-serif',
    h4: { fontWeight: 800, letterSpacing: "-0.035em" },
    h5: { fontWeight: 750, letterSpacing: "-0.025em" },
    h6: { fontWeight: 750, letterSpacing: "-0.02em" },
    subtitle2: { fontWeight: 650 },
    button: { textTransform: "none", fontWeight: 650, letterSpacing: 0 },
    overline: { fontWeight: 750, letterSpacing: "0.09em" },
  },
  shadows: [
    "none",
    "0 1px 2px rgba(16,24,40,0.04)",
    "0 2px 5px rgba(16,24,40,0.05)",
    "0 4px 10px rgba(16,24,40,0.06)",
    "0 8px 18px rgba(16,24,40,0.07)",
    ...Array(20).fill("0 12px 28px rgba(16,24,40,0.08)"),
  ],
  components: {
    MuiCssBaseline: {
      styleOverrides: {
        "html, body, #root": { minHeight: "100%", width: "100%" },
        body: {
          backgroundColor: "#f5f7fb",
          backgroundImage: "radial-gradient(ellipse at 12% 0%, rgba(94,14,215,0.045), transparent 38%)",
          WebkitFontSmoothing: "antialiased",
        },
        "::selection": { background: "rgba(94,14,215,0.18)" },
        "*:focus-visible": { outline: "3px solid rgba(94,14,215,0.45)", outlineOffset: 2 },
        "@keyframes mq-fade-up": {
          from: { opacity: 0, transform: "translateY(22px)" },
          to: { opacity: 1, transform: "translateY(0)" },
        },
        "@keyframes mq-fade-in": {
          from: { opacity: 0 },
          to: { opacity: 1 },
        },
        "@keyframes mq-float": {
          "0%, 100%": { transform: "translateY(0)" },
          "50%": { transform: "translateY(-10px)" },
        },
        ".mq-rise": { animation: "mq-fade-up 700ms cubic-bezier(0.22,1,0.36,1) both" },
        ".mq-card-in": {
          animation: "mq-fade-up 600ms cubic-bezier(0.22,1,0.36,1) both",
          "animation-delay": "inherit",
        },
        ".mq-row-in": {
          animation: "mq-fade-up 480ms cubic-bezier(0.22,1,0.36,1) both",
        },
        ".mq-float": {
          animation: "mq-float 7s ease-in-out infinite",
        },
        ".mq-blur": {
          backdropFilter: "blur(14px)",
          backgroundColor: "rgba(255,255,255,0.82)",
        },
      },
    },
    MuiCard: {
      styleOverrides: {
        root: {
          border: "1px solid #e6eaf0",
          boxShadow: "0 2px 8px rgba(16,24,40,0.035)",
          backgroundImage: "none",
          transition: "border-color 160ms ease, box-shadow 160ms ease, transform 160ms ease",
        },
      },
    },
    MuiButton: {
      styleOverrides: {
        root: { borderRadius: 10, boxShadow: "none", minHeight: 38 },
        contained: { "&:hover": { boxShadow: "0 5px 14px rgba(94,14,215,0.18)" } },
      },
    },
    MuiIconButton: {
      styleOverrides: {
        root: { transition: "background-color 160ms ease, color 160ms ease" },
      },
    },
    MuiChip: { styleOverrides: { root: { fontWeight: 650, borderRadius: 8 } } },
    MuiTableContainer: { styleOverrides: { root: { borderRadius: "0 0 14px 14px" } } },
    MuiTableCell: {
      styleOverrides: {
        root: { borderColor: "#edf0f5", paddingTop: 12, paddingBottom: 12 },
        head: {
          fontWeight: 750,
          color: "#596579",
          backgroundColor: "#faf7ff",
          fontSize: "0.72rem",
          letterSpacing: "0.045em",
          textTransform: "uppercase",
          whiteSpace: "nowrap",
        },
      },
    },
    MuiTableRow: {
      styleOverrides: {
        root: { "&:last-child td": { borderBottom: 0 } },
      },
    },
    MuiTextField: {
      defaultProps: { size: "small" },
    },
  },
});
