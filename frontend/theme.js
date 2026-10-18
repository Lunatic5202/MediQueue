import { createTheme } from "@mui/material/styles";

const primary = { main: "#2563eb", dark: "#1d4ed8", light: "#60a5fa" };
const success = { main: "#059669" };
const warning = { main: "#d97706" };
const error = { main: "#dc2626" };
const info = { main: "#0891b2" };

export const riskColors = {
  low: "#059669",
  watch: "#0891b2",
  elevated: "#d97706",
  high: "#dc2626",
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
    background: { default: "#f4f6fb", paper: "#ffffff" },
    text: { primary: "#1e293b", secondary: "#64748b" },
    divider: "#e2e8f0",
  },
  shape: { borderRadius: 12 },
  typography: {
    fontFamily: '"Inter", "Segoe UI", system-ui, -apple-system, sans-serif',
    h5: { fontWeight: 700 },
    h6: { fontWeight: 700 },
    subtitle2: { fontWeight: 600 },
    button: { textTransform: "none", fontWeight: 600 },
  },
  shadows: [
    "none",
    "0 1px 2px rgba(15,23,42,0.06)",
    "0 1px 3px rgba(15,23,42,0.08)",
    "0 2px 6px rgba(15,23,42,0.08)",
    "0 4px 12px rgba(15,23,42,0.10)",
    ...Array(20).fill("0 8px 24px rgba(15,23,42,0.12)"),
  ],
  components: {
    MuiCard: {
      styleOverrides: {
        root: { border: "1px solid #e2e8f0", boxShadow: "0 1px 3px rgba(15,23,42,0.06)" },
      },
    },
    MuiButton: { styleOverrides: { root: { borderRadius: 8, boxShadow: "none" } } },
    MuiChip: { styleOverrides: { root: { fontWeight: 600 } } },
    MuiTableHead: {
      styleOverrides: {
        root: { "& .MuiTableCell-root": { fontWeight: 700, color: "#475569", background: "#f8fafc" } },
      },
    },
  },
});
