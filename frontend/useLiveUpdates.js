import { useCallback, useEffect, useRef, useState } from "react";
import { getToken } from "./api";

/**
 * Live updates: WebSocket with automatic fallback to polling.
 * Exposes { connected, transport, lastEvent, bump } — `bump` invalidates
 * consumers after any queue/alert/risk event; pages refetch on `lastEvent`.
 */
export function useLiveUpdates() {
  const [transport, setTransport] = useState("connecting"); // connecting | websocket | polling
  const [lastEvent, setLastEvent] = useState(0);
  const [wsHealthy, setWsHealthy] = useState(false);
  const pollRef = useRef(null);
  const wsRef = useRef(null);
  const sinceIdRef = useRef(0);
  const deadRef = useRef(false);

  const bump = useCallback(() => setLastEvent(Date.now()), []);

  useEffect(() => {
    deadRef.current = false;
    let retryTimer = null;

    const startPolling = () => {
      if (pollRef.current || deadRef.current) return;
      setTransport("polling");
      pollRef.current = setInterval(async () => {
        try {
          const token = getToken();
          if (!token) return;
          const resp = await fetch(`/api/events?since_id=${sinceIdRef.current}&limit=200`, {
            headers: { Authorization: `Bearer ${token}` },
          });
          if (!resp.ok) return;
          const data = await resp.json();
          const events = data.events ?? data;
          if (Array.isArray(events) && events.length) {
            sinceIdRef.current = events[events.length - 1].id;
            setLastEvent(Date.now());
          }
        } catch {
          /* transient network failures: keep polling */
        }
      }, 3000);
    };

    const stopPolling = () => {
      if (pollRef.current) {
        clearInterval(pollRef.current);
        pollRef.current = null;
      }
    };

    const connect = () => {
      if (deadRef.current) return;
      const token = getToken();
      if (!token) {
        setTransport("polling");
        return;
      }
      const proto = window.location.protocol === "https:" ? "wss" : "ws";
      let ws;
      try {
        ws = new WebSocket(`${proto}://${window.location.host}/ws?token=${encodeURIComponent(token)}`);
      } catch {
        startPolling();
        return;
      }
      wsRef.current = ws;
      setTransport("connecting");

      const fallbackTimer = setTimeout(() => {
        if (ws.readyState !== WebSocket.OPEN) startPolling();
      }, 2500);

      ws.onopen = () => {
        clearTimeout(fallbackTimer);
        stopPolling();
        setTransport("websocket");
        setWsHealthy(true);
      };
      ws.onmessage = (msg) => {
        try {
          const data = JSON.parse(msg.data);
          if (data.type === "hello") return;
          const events = Array.isArray(data.events) ? data.events : [data];
          const last = events[events.length - 1];
          if (last?.id) sinceIdRef.current = Math.max(sinceIdRef.current, last.id);
          setLastEvent(Date.now());
        } catch {
          /* ignore malformed frames */
        }
      };
      ws.onclose = () => {
        clearTimeout(fallbackTimer);
        setWsHealthy(false);
        if (deadRef.current) return;
        startPolling();
        retryTimer = setTimeout(connect, 5000);
      };
      ws.onerror = () => {
        try {
          ws.close();
        } catch {
          /* noop */
        }
      };
    };

    connect();
    return () => {
      deadRef.current = true;
      clearTimeout(retryTimer);
      stopPolling();
      if (wsRef.current) {
        try {
          wsRef.current.close();
        } catch {
          /* noop */
        }
      }
    };
  }, []);

  return { transport, connected: transport === "websocket" && wsHealthy, lastEvent, bump };
}
