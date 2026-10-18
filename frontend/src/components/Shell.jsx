import { useState } from "react";
import { NavLink, Outlet, useNavigate } from "react-router-dom";
import {
  AppBar,
  Box,
  Divider,
  Drawer,
  IconButton,
  List,
  ListItemButton,
  ListItemIcon,
  ListItemText,
  Toolbar,
  Typography,
  Avatar,
  Menu,
  MenuItem,
  Chip,
  Stack,
  Tooltip,
  useMediaQuery,
  useTheme,
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

const WIDTH = 248;

const NAV = [
  { to: "/", label: "Live Queue", icon: <DashboardIcon />, end: true },
  { to: "/alerts", label: "Alerts", icon: <NotificationsActiveIcon /> },
  { to: "/audit", label: "Audit Trail", icon: <GavelIcon /> },
  { to: "/replay", label: "Replay Simulator", icon: <ReplayIcon /> },
  { to: "/model", label: "Model & Health", icon: <HealthAndSafetyIcon /> },
];

export default function Shell({ transport, connected }) {
  const theme = useTheme();
  const isDesktop = useMediaQuery(theme.breakpoints.up("lg"));
  const [mobileOpen, setMobileOpen] = useState(false);
  const [anchorEl, setAnchorEl] = useState(null);
  const { user, logout } = useAuth();
  const navigate = useNavigate();

  const drawer = (
    <Box sx={{ height: "100%", background: "linear-gradient(180deg,#0f172a 0%,#1e293b 100%)" }}>
      <Box sx={{ px: 3, py: 2.5, display: "flex", alignItems: "center", gap: 1.5 }}>
        <Box
          sx={{
            width: 38,
            height: 38,
            borderRadius: 2,
            background: "linear-gradient(135deg,#2563eb,#7c3aed)",
            display: "grid",
            placeItems: "center",
            color: "white",
          }}
        >
          <HealthAndSafetyIcon />
        </Box>
        <Box>
          <Typography sx={{ color: "white", fontWeight: 800, fontSize: 17, lineHeight: 1.1 }}>
            MediQueue
          </Typography>
          <Typography sx={{ color: "#94a3b8", fontSize: 11.5 }}>ED Decision Support</Typography>
        </Box>
      </Box>
      <Divider sx={{ borderColor: "#334155", mx: 2 }} />
      <List sx={{ px: 2, pt: 2 }}>
        {NAV.map((item) => (
          <ListItemButton
            key={item.to}
            component={NavLink}
            to={item.to}
            end={item.end}
            onClick={() => setMobileOpen(false)}
            sx={{
              mb: 0.5,
              borderRadius: 2,
              color: "#cbd5e1",
              "&.active": {
                background: "linear-gradient(90deg,#2563eb33,#2563eb14)",
                color: "white",
                boxShadow: "inset 3px 0 0 #2563eb",
              },
              "&:hover": { background: "#ffffff10", color: "white" },
            }}
          >
            <ListItemIcon sx={{ minWidth: 36, color: "inherit" }}>{item.icon}</ListItemIcon>
            <ListItemText primary={item.label} primaryTypographyProps={{ fontSize: 14, fontWeight: 600 }} />
          </ListItemButton>
        ))}
      </List>
      <Box sx={{ position: "absolute", bottom: 0, left: 0, right: 0, p: 2 }}>
        <Divider sx={{ borderColor: "#334155", mb: 2 }} />
        <Stack direction="row" spacing={1} alignItems="center" sx={{ px: 1 }}>
          <CircleIcon
            sx={{
              fontSize: 10,
              color: connected ? "#34d399" : transport === "polling" ? "#fbbf24" : "#f87171",
            }}
          />
          <Typography sx={{ color: "#94a3b8", fontSize: 12 }}>
            {transport === "websocket"
              ? "Live · WebSocket"
              : transport === "polling"
                ? "Fallback · Polling"
                : "Connecting…"}
          </Typography>
        </Stack>
      </Box>
    </Box>
  );

  return (
    <Box sx={{ display: "flex", minHeight: "100vh", background: "background.default" }}>
      <Box component="nav" sx={{ width: WIDTH, flexShrink: 0 }}>
        {isDesktop ? (
          <Drawer variant="persistent" open PaperProps={{ sx: { width: WIDTH, border: "none" } }}>
            {drawer}
          </Drawer>
        ) : (
          <Drawer open={mobileOpen} onClose={() => setMobileOpen(false)} PaperProps={{ sx: { width: WIDTH } }}>
            {drawer}
          </Drawer>
        )}
      </Box>
      <Box sx={{ flex: 1, display: "flex", flexDirection: "column", minWidth: 0 }}>
        <AppBar
          elevation={0}
          position="sticky"
          sx={{ background: "rgba(255,255,255,0.85)", backdropFilter: "blur(8px)", borderBottom: "1px solid", borderColor: "divider" }}
        >
          <Toolbar sx={{ gap: 1.5 }}>
            {!isDesktop && (
              <IconButton onClick={() => setMobileOpen(true)} edge="start">
                <MenuIcon />
              </IconButton>
            )}
            <Typography variant="h6" sx={{ flex: 1, color: "text.primary" }}>
              Emergency Department · Live Operations
            </Typography>
            <Chip
              size="small"
              label="Decision support only"
              sx={{ bgcolor: "#fef3c7", color: "#92400e", border: "1px solid #fcd34d", fontWeight: 700 }}
            />
            <Tooltip title="Account">
              <IconButton onClick={(e) => setAnchorEl(e.currentTarget)} size="small">
                <Avatar sx={{ width: 34, height: 34, bgcolor: "primary.main", fontSize: 14 }}>
                  {user?.username?.[0]?.toUpperCase() ?? "?"}
                </Avatar>
              </IconButton>
            </Tooltip>
            <Menu anchorEl={anchorEl} open={Boolean(anchorEl)} onClose={() => setAnchorEl(null)}>
              <MenuItem disabled>
                <PersonIcon fontSize="small" sx={{ mr: 1 }} /> {user?.username} · {user?.role}
              </MenuItem>
              <Divider />
              <MenuItem
                onClick={() => {
                  setAnchorEl(null);
                  logout();
                  navigate("/login");
                }}
              >
                <LogoutIcon fontSize="small" sx={{ mr: 1 }} /> Sign out
              </MenuItem>
            </Menu>
          </Toolbar>
        </AppBar>
        <Box component="main" sx={{ flex: 1, p: { xs: 2, md: 3 } }}>
          <Outlet />
        </Box>
      </Box>
    </Box>
  );
}
