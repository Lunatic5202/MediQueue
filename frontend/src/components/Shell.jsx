import { useState } from "react";
import { NavLink, Outlet, useLocation, useNavigate } from "react-router-dom";
import {
  AppBar, Box, Divider, Drawer, IconButton, List, ListItemButton, ListItemIcon,
  ListItemText, Toolbar, Typography, Avatar, Menu, MenuItem, Chip, Stack,
  Tooltip, useMediaQuery, useTheme,
} from "@mui/material";
import MenuIcon from "@mui/icons-material/Menu";
import DashboardIcon from "@mui/icons-material/Dashboard";
import NotificationsActiveIcon from "@mui/icons-material/NotificationsActive";
import GavelIcon from "@mui/icons-material/Gavel";
import ReplayIcon from "@mui/icons-material/Replay";
import HealthAndSafetyIcon from "@mui/icons-material/HealthAndSafety";
import PersonIcon from "@mui/icons-material/Person";
import LogoutIcon from "@mui/icons-material/Logout";
import CircleIcon from "@mui/icons-material/Circle";
import { useAuth } from "../auth";

const WIDTH = 256;
const NAV = [
  { to: "/", label: "Live Queue", icon: <DashboardIcon />, end: true },
  { to: "/alerts", label: "Alerts", icon: <NotificationsActiveIcon /> },
  { to: "/audit", label: "Audit Trail", icon: <GavelIcon /> },
  { to: "/replay", label: "Replay Simulator", icon: <ReplayIcon /> },
  { to: "/model", label: "Model & Health", icon: <HealthAndSafetyIcon /> },
];
const PAGE_LABELS = {
  "/": ["Live operations", "Emergency department overview"],
  "/alerts": ["Alert center", "Review deterioration signals and their current status"],
  "/audit": ["Audit trail", "Trace important actions and system events"],
  "/replay": ["Replay simulator", "Explore system behavior with synthetic scenarios"],
  "/model": ["Model & system health", "Service status, model information and safeguards"],
};

export default function Shell({ transport, connected }) {
  const theme = useTheme();
  const isDesktop = useMediaQuery(theme.breakpoints.up("lg"));
  const isSmall = useMediaQuery(theme.breakpoints.down("sm"));
  const location = useLocation();
  const [mobileOpen, setMobileOpen] = useState(false);
  const [anchorEl, setAnchorEl] = useState(null);
  const { user, logout } = useAuth();
  const navigate = useNavigate();
  const page = location.pathname.startsWith("/patients/")
    ? ["Patient overview", "Vitals, risk history and clinician recommendations"]
    : (PAGE_LABELS[location.pathname] ?? PAGE_LABELS["/"]);
  const statusColor = connected ? "#34d399" : transport === "polling" ? "#fbbf24" : "#fb7185";
  const transportLabel = transport === "websocket"
    ? "Live connection"
    : transport === "polling"
      ? "Polling fallback"
      : "Connecting";

  const drawer = (
    <Box sx={{ height: "100%", display: "flex", flexDirection: "column", color: "white", background: "linear-gradient(165deg,#101a31 0%,#14223d 55%,#182b49 100%)" }}>
      <Box sx={{ px: 2.5, py: 2.75, display: "flex", alignItems: "center", gap: 1.5 }}>
        <Box sx={{ width: 42, height: 42, flexShrink: 0, borderRadius: "13px", background: "linear-gradient(140deg,#60a5fa,#2563eb 58%,#4f46e5)", display: "grid", placeItems: "center", boxShadow: "0 7px 18px #2563eb55" }}>
          <HealthAndSafetyIcon sx={{ fontSize: 25 }} />
        </Box>
        <Box>
          <Typography sx={{ color: "white", fontWeight: 850, fontSize: 18, letterSpacing: "-0.04em", lineHeight: 1.1 }}>MediQueue</Typography>
          <Typography sx={{ color: "#9aacc8", fontSize: 11.5, mt: 0.5 }}>ED decision support</Typography>
        </Box>
      </Box>
      <Divider sx={{ borderColor: "#ffffff14", mx: 2 }} />
      <Typography sx={{ px: 3, pt: 3, pb: 1.25, color: "#7186a8", fontSize: 10, fontWeight: 800, letterSpacing: "0.14em" }}>WORKSPACE</Typography>
      <List sx={{ px: 1.5, pt: 0 }}>
        {NAV.map((item) => (
          <ListItemButton
            key={item.to}
            component={NavLink}
            to={item.to}
            end={item.end}
            onClick={() => setMobileOpen(false)}
            sx={{
              mb: 0.65, minHeight: 46, borderRadius: 2.5, px: 1.5, color: "#b8c6dc",
              transition: "background 160ms ease, color 160ms ease, transform 160ms ease",
              "& .MuiListItemIcon-root": { transition: "color 160ms ease" },
              "&.active": { background: "linear-gradient(100deg,#3478f633,#3478f610)", color: "#fff", boxShadow: "inset 3px 0 0 #60a5fa" },
              "&.active .MuiListItemIcon-root": { color: "#8ec5ff" },
              "&:hover": { background: "#ffffff0d", color: "#fff", transform: "translateX(2px)" },
            }}
          >
            <ListItemIcon sx={{ minWidth: 38, color: "inherit" }}>{item.icon}</ListItemIcon>
            <ListItemText primary={item.label} primaryTypographyProps={{ fontSize: 13.5, fontWeight: 650 }} />
          </ListItemButton>
        ))}
      </List>
      <Box sx={{ mt: "auto", p: 2 }}>
        <Box sx={{ p: 1.75, borderRadius: 3, background: "#ffffff08", border: "1px solid #ffffff12" }}>
          <Stack direction="row" alignItems="center" spacing={1}>
            <CircleIcon sx={{ fontSize: 9, color: statusColor }} />
            <Typography sx={{ color: "#d5deec", fontSize: 11.5, fontWeight: 700 }}>{transportLabel}</Typography>
          </Stack>
          <Typography sx={{ color: "#8498b8", fontSize: 10.5, mt: 0.75, lineHeight: 1.5 }}>
            {transport === "websocket" ? "Real-time event stream enabled" : transport === "polling" ? "Updates are using the polling fallback" : "Establishing a secure session"}
          </Typography>
        </Box>
        <Typography sx={{ color: "#7084a4", fontSize: 10.5, px: 0.5, pt: 2, lineHeight: 1.6 }}>
          Research prototype · Clinician oversight required
        </Typography>
      </Box>
    </Box>
  );

  return (
    <Box sx={{ display: "flex", minHeight: "100vh", backgroundColor: "background.default" }}>
      <Box component="nav" sx={{ width: isDesktop ? WIDTH : 0, flexShrink: 0 }}>
        {isDesktop ? (
          <Drawer variant="permanent" open PaperProps={{ sx: { width: WIDTH, border: "none", boxSizing: "border-box", boxShadow: "5px 0 24px rgba(16,24,40,0.04)" } }}>
            {drawer}
          </Drawer>
        ) : (
          <Drawer variant="temporary" open={mobileOpen} onClose={() => setMobileOpen(false)} ModalProps={{ keepMounted: true }} PaperProps={{ sx: { width: WIDTH, border: "none" } }}>
            {drawer}
          </Drawer>
        )}
      </Box>
      <Box sx={{ flex: 1, display: "flex", flexDirection: "column", minWidth: 0 }}>
        <AppBar elevation={0} position="sticky" sx={{ background: "rgba(255,255,255,0.9)", backdropFilter: "blur(16px)", borderBottom: "1px solid", borderColor: "divider", color: "text.primary" }}>
          <Toolbar sx={{ gap: { xs: 1, sm: 1.75 }, minHeight: { xs: 64, sm: 76 }, px: { xs: 2, md: 3 } }}>
            {!isDesktop && <IconButton onClick={() => setMobileOpen(true)} edge="start" aria-label="Open navigation"><MenuIcon /></IconButton>}
            <Box sx={{ flex: 1, minWidth: 0 }}>
              <Typography sx={{ fontWeight: 800, fontSize: { xs: 15, sm: 17 }, letterSpacing: "-0.025em", lineHeight: 1.25 }} noWrap>{page[0]}</Typography>
              {!isSmall && <Typography variant="caption" color="text.secondary" sx={{ display: "block", mt: 0.4 }} noWrap>{page[1]}</Typography>}
            </Box>
            {!isSmall && <Chip size="small" label="Decision support only" sx={{ bgcolor: "#fff7e6", color: "#92400e", border: "1px solid #f5d79a", fontWeight: 750 }} />}
            <Tooltip title={transportLabel}>
              <Chip size="small" icon={<CircleIcon sx={{ fontSize: "9px !important", color: statusColor }} />} label={isSmall ? (connected ? "Live" : "Offline") : transportLabel} variant="outlined" sx={{ bgcolor: connected ? "#f0fdf6" : "#fffaf0", borderColor: connected ? "#bbf7d0" : "#fde68a", color: connected ? "#166534" : "#92400e", "& .MuiChip-label": { px: 1, fontSize: 11, fontWeight: 750 } }} />
            </Tooltip>
            <Tooltip title="Account">
              <IconButton onClick={(e) => setAnchorEl(e.currentTarget)} size="small" aria-label="Account menu">
                <Avatar sx={{ width: 36, height: 36, bgcolor: "primary.main", fontSize: 14, fontWeight: 800, boxShadow: "0 0 0 3px #2563eb14" }}>{user?.username?.[0]?.toUpperCase() ?? "?"}</Avatar>
              </IconButton>
            </Tooltip>
            <Menu anchorEl={anchorEl} open={Boolean(anchorEl)} onClose={() => setAnchorEl(null)}>
              <MenuItem disabled><PersonIcon fontSize="small" sx={{ mr: 1 }} />{user?.username} · {user?.role}</MenuItem>
              <Divider />
              <MenuItem onClick={() => { setAnchorEl(null); logout(); navigate("/login"); }}>
                <LogoutIcon fontSize="small" sx={{ mr: 1 }} /> Sign out
              </MenuItem>
            </Menu>
          </Toolbar>
        </AppBar>
        <Box component="main" sx={{ flex: 1, width: "100%", maxWidth: 1800, mx: "auto", p: { xs: 2, sm: 2.5, lg: 3.5 } }}>
          <Outlet />
        </Box>
      </Box>
    </Box>
  );
}
