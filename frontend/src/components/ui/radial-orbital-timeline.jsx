import { useEffect, useMemo, useRef, useState } from "react";
import { motion, AnimatePresence } from "framer-motion";
import { Card, CardContent, CardHeader, CardTitle } from "@/components/ui/card";
import { Badge } from "@/components/ui/badge";
import { Button } from "@/components/ui/button";
import { cn } from "@/lib/utils";

const STATUS_STYLES = {
  completed: {
    badge: "bg-emerald-500/15 text-emerald-300 border-emerald-500/30",
    ring: "border-emerald-400/60",
    dot: "bg-emerald-400",
  },
  active: {
    badge: "bg-blue-500/15 text-blue-300 border-blue-500/30",
    ring: "border-blue-400/60",
    dot: "bg-blue-400",
  },
  pending: {
    badge: "bg-amber-500/15 text-amber-300 border-amber-500/30",
    ring: "border-amber-400/60",
    dot: "bg-amber-400",
  },
};

const RADIUS = { mobile: 130, desktop: 200 };

function polarToCartesian(radius, angleDeg) {
  const rad = ((angleDeg - 90) * Math.PI) / 180;
  return { x: radius * Math.cos(rad), y: radius * Math.sin(rad) };
}

/**
 * RadialOrbitalTimeline — JSX port of the 21st.dev component.
 * Shows MediQueue's pipeline stages as an orbital ring. Adapted from the
 * original: lucide icons (no emoji), @/ui primitives, mobile-safe radius.
 */
export default function RadialOrbitalTimeline({
  data = [],
  centerTitle = "Pipeline",
  centerSubtitle = "Live",
  className,
}) {
  const [selected, setSelected] = useState(null);
  const [rotation, setRotation] = useState(0);
  const [radius, setRadius] = useState(RADIUS.mobile);
  const rafRef = useRef(null);
  const lastTsRef = useRef(null);

  useEffect(() => {
    const onResize = () => setRadius(window.innerWidth < 768 ? RADIUS.mobile : RADIUS.desktop);
    onResize();
    window.addEventListener("resize", onResize);
    return () => window.removeEventListener("resize", onResize);
  }, []);

  useEffect(() => {
    const animate = (ts) => {
      if (lastTsRef.current == null) lastTsRef.current = ts;
      const dt = ts - lastTsRef.current;
      lastTsRef.current = ts;
      setRotation((r) => (r + dt * 0.004) % 360);
      rafRef.current = requestAnimationFrame(animate);
    };
    rafRef.current = requestAnimationFrame(animate);
    return () => {
      if (rafRef.current) cancelAnimationFrame(rafRef.current);
      lastTsRef.current = null;
    };
  }, []);

  const n = data.length;
  const nodes = useMemo(() => {
    return data.map((item, i) => {
      const baseAngle = (360 / n) * i;
      const angle = baseAngle + rotation;
      const pos = polarToCartesian(radius, angle);
      return { item, angle, x: pos.x, y: pos.y };
    });
  }, [data, n, rotation, radius]);

  const active = selected != null ? data.find((d) => d.id === selected) : null;

  return (
    <div className={cn("relative w-full", className)}>
      <div className="relative mx-auto flex h-[420px] w-full max-w-3xl items-center justify-center sm:h-[520px]">
        {/* orbital rings */}
        <div
          className="absolute rounded-full border border-white/10"
          style={{ width: radius * 2, height: radius * 2 }}
        />
        <div
          className="absolute rounded-full border border-white/5"
          style={{ width: radius * 1.4, height: radius * 1.4 }}
        />

        {/* center hub */}
        <div className="absolute z-10 flex h-24 w-24 flex-col items-center justify-center rounded-full border border-white/15 bg-white/5 backdrop-blur">
          <span className="text-[10px] uppercase tracking-widest text-white/50">
            {centerSubtitle}
          </span>
          <span className="mt-1 text-sm font-semibold uppercase tracking-widest text-white">
            {centerTitle}
          </span>
        </div>

        {/* nodes */}
        {nodes.map(({ item, x, y }) => {
          const st = STATUS_STYLES[item.status] || STATUS_STYLES.pending;
          const isActive = selected === item.id;
          return (
            <button
              key={item.id}
              type="button"
              onClick={() => setSelected(isActive ? null : item.id)}
              className="absolute flex h-14 w-14 flex-col items-center justify-center rounded-full border bg-neutral-900/80 backdrop-blur transition-transform hover:scale-110 focus:outline-none"
              style={{
                transform: `translate(${x}px, ${y}px)`,
                borderColor: isActive ? "rgba(94,14,215,0.9)" : "rgba(255,255,255,0.18)",
              }}
              aria-label={item.title}
              aria-pressed={isActive}
            >
              <span
                className={cn(
                  "absolute -right-0.5 -top-0.5 h-2.5 w-2.5 rounded-full",
                  st.dot,
                )}
              />
              <item.icon className="h-5 w-5 text-white" />
            </button>
          );
        })}

        {/* connecting lines */}
        <svg
          className="pointer-events-none absolute inset-0 h-full w-full"
          style={{ overflow: "visible" }}
        >
          {nodes.map(({ item, x, y }) => (
            <line
              key={`line-${item.id}`}
              x1="50%"
              y1="50%"
              x2={`calc(50% + ${x}px)`}
              y2={`calc(50% + ${y}px)`}
              stroke="rgba(255,255,255,0.08)"
              strokeWidth="1"
            />
          ))}
        </svg>
      </div>

      {/* detail panel */}
      <div className="mx-auto mt-6 min-h-[190px] max-w-3xl px-5 sm:px-8">
        <AnimatePresence mode="wait">
          {active ? (
            <motion.div
              key={active.id}
              initial={{ opacity: 0, y: 12 }}
              animate={{ opacity: 1, y: 0 }}
              exit={{ opacity: 0, y: -12 }}
              transition={{ duration: 0.35, ease: [0.22, 1, 0.36, 1] }}
            >
              <Card className="border-white/10 bg-white/5 text-white">
                <CardHeader className="flex-row items-center justify-between space-y-0">
                  <div className="flex items-center gap-3">
                    <active.icon className="h-5 w-5" style={{ color: "#5E0ED7" }} />
                    <CardTitle className="text-sm uppercase tracking-widest text-white">
                      {active.title}
                    </CardTitle>
                  </div>
                  <Badge
                    variant="outline"
                    className={cn("uppercase tracking-widest", STATUS_STYLES[active.status].badge)}
                  >
                    {active.status}
                  </Badge>
                </CardHeader>
                <CardContent>
                  <p className="text-[11px] leading-relaxed tracking-wide normal-case text-white/60">
                    {active.detail}
                  </p>
                  <Button
                    variant="ghost"
                    size="sm"
                    onClick={() => setSelected(null)}
                    className="mt-4 text-white/60 hover:text-white"
                  >
                    Close
                  </Button>
                </CardContent>
              </Card>
            </motion.div>
          ) : (
            <motion.p
              key="hint"
              initial={{ opacity: 0 }}
              animate={{ opacity: 1 }}
              exit={{ opacity: 0 }}
              className="pt-8 text-center text-[11px] uppercase tracking-widest text-white/40"
            >
              Tap a stage to inspect it
            </motion.p>
          )}
        </AnimatePresence>
      </div>
    </div>
  );
}
