import { useEffect } from "react";
import { Navigate, Route, Routes } from "react-router-dom";
import { useAuth } from "./auth";
import Shell from "./components/Shell";
import LandingPage from "./pages/LandingPage";
import MedLanding from "./pages/MedLanding";
import LoginPage from "./pages/LoginPage";
import QueuePage from "./pages/QueuePage";
import PatientPage from "./pages/PatientPage";
import AlertsPage from "./pages/AlertsPage";
import AuditPage from "./pages/AuditPage";
import ReplayPage from "./pages/ReplayPage";
import ModelPage from "./pages/ModelPage";
import { useLiveUpdates } from "./useLiveUpdates";
import { publishLiveEvent } from "./liveBridge";
import { useLiveEvent, bumpLive } from "./useLiveEvent";
import { LinearProgress, Box } from "@mui/material";

function Protected({ children }) {
  const { user, ready } = useAuth();
  if (!ready)
    return (
      <Box sx={{ p: 4 }}>
        <LinearProgress />
      </Box>
    );
  if (!user) return <Navigate to="/login" replace />;
  return children;
}

function LiveShell() {
  const { transport, connected, lastEvent } = useLiveUpdates();
  useEffect(() => {
    if (lastEvent) publishLiveEvent(lastEvent);
  }, [lastEvent]);
  return <Shell transport={transport} connected={connected} />;
}

export default function App() {
  const { user, ready } = useAuth();

  return (
    <Routes>
      <Route
        path="/"
        element={
          !ready ? (
            <Box sx={{ p: 4 }}>
              <LinearProgress />
            </Box>
          ) : user ? (
            <Navigate to="/queue" replace />
          ) : (
            <MedLanding />
          )
        }
      />
      <Route path="/old" element={<LandingPage />} />
      <Route path="/login" element={user ? <Navigate to="/queue" replace /> : <LoginPage />} />
      <Route
        element={
          <Protected>
            <LiveShell />
          </Protected>
        }
      >
        <Route path="/queue" element={<QueuePageWithLive />} />
        <Route path="/patients/:patientId" element={<PatientWithLive />} />
        <Route path="/alerts" element={<AlertsWithLive />} />
        <Route path="/audit" element={<AuditPage />} />
        <Route path="/replay" element={<ReplayWithLive />} />
        <Route path="/model" element={<ModelPage />} />
      </Route>
      <Route path="*" element={<Navigate to="/" replace />} />
    </Routes>
  );
}

function QueuePageWithLive() {
  const lastEvent = useLiveEvent();
  return <QueuePage lastEvent={lastEvent} />;
}
function PatientWithLive() {
  const lastEvent = useLiveEvent();
  return <PatientPage lastEvent={lastEvent} onAction={bumpLive} />;
}
function AlertsWithLive() {
  const lastEvent = useLiveEvent();
  return <AlertsPage lastEvent={lastEvent} />;
}
function ReplayWithLive() {
  const lastEvent = useLiveEvent();
  return <ReplayPage lastEvent={lastEvent} onAction={bumpLive} />;
}
