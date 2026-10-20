import { useEffect, useState } from "react";
import { Link } from "react-router-dom";
import { motion } from "framer-motion";
import {
  Activity,
  ArrowUpRight,
  Bell,
  Brain,
  ClipboardCheck,
  FileText,
  Layers,
  ShieldCheck,
  TrendingUp,
  X,
} from "lucide-react";
import ScrollExpandMedia from "@/components/ui/scroll-expansion-hero";
import RadialOrbitalTimeline from "@/components/ui/radial-orbital-timeline";
import FlexCarousel from "@/components/FlexCarousel";
import TiltedCard from "@/components/TiltedCard";

const VIDEO_URL =
  "https://d8j0ntlcm91z4.cloudfront.net/user_38xzZboKViGWJOttwIXH07lWA1P/hf_20260517_222138_3e3205be-3364-417b-a64a-bfe087acbec4.mp4";
const BG_IMAGE =
  "https://images.unsplash.com/photo-1519494026892-80bbd2d6fd0d?auto=format&fit=crop&w=1920&q=80";
const ACCENT = "#5E0ED7";
const EASE = [0.22, 1, 0.36, 1];

const MotionLink = motion(Link);

const fadeDown = {
  hidden: { opacity: 0, y: -20 },
  show: (i = 0) => ({
    opacity: 1,
    y: 0,
    transition: { delay: i * 0.1, duration: 0.5, ease: EASE },
  }),
};

const fadeUp = {
  hidden: { opacity: 0, y: 32 },
  show: (i = 0) => ({
    opacity: 1,
    y: 0,
    transition: { delay: i * 0.12, duration: 0.6, ease: EASE },
  }),
};

const NAV_LINKS = [
  { label: "Platform", href: "#platform" },
  { label: "Pipeline", href: "#pipeline" },
  { label: "Safety", href: "#safety" },
  { label: "Model", href: "#model" },
];

const STATS = [
  { plus: true, n: "4", a: "CORE\nVITALS" },
  { plus: false, n: "4H", a: "ROLLING\nWINDOW" },
  { plus: false, n: "100%", a: "DECISIONS\nAUDITED" },
];

const headingWords = ["Watch", "Warn", "Decide"];

const PIPELINE = [
  {
    id: 1,
    title: "Ingest",
    status: "completed",
    icon: Activity,
    detail:
      "Heart rate, SpO2, blood pressure and temperature stream in from bed monitors or the replay simulator, each carrying an idempotency key so retried events never double-count.",
  },
  {
    id: 2,
    title: "Validate",
    status: "completed",
    icon: ShieldCheck,
    detail:
      "Strict unit normalization and range checks reject ambiguous or impossible values at the door. Anything out of physiologic bounds is dropped, never guessed.",
  },
  {
    id: 3,
    title: "Window",
    status: "completed",
    icon: Layers,
    detail:
      "A rolling four-hour history is built per patient: reading counts, latest values, deltas, slopes and shock index become the model's feature vector.",
  },
  {
    id: 4,
    title: "Score",
    status: "completed",
    icon: Brain,
    detail:
      "Class-weighted LightGBM scores deterioration risk. With too little history the model abstains — the UI shows no score rather than a false safe.",
  },
  {
    id: 5,
    title: "Trend",
    status: "completed",
    icon: TrendingUp,
    detail:
      "Deterministic adverse-trend rules run alongside the model, catching abrupt drops and sustained declines that a single reading would miss.",
  },
  {
    id: 6,
    title: "Alert",
    status: "completed",
    icon: Bell,
    detail:
      "Deduplicated alerts with cooldown windows and a material-worsening bypass, delivered over a live WebSocket with an automatic polling fallback.",
  },
  {
    id: 7,
    title: "Recommend",
    status: "active",
    icon: ClipboardCheck,
    detail:
      "Bounded ESI recommendations — at most one category per confirm — wait for a clinician to confirm, reject or override, each with a mandatory rationale.",
  },
  {
    id: 8,
    title: "Audit",
    status: "pending",
    icon: FileText,
    detail:
      "Every decision and pipeline event lands in an append-only audit trail written in the same transaction. If the audit write fails, the whole action rolls back.",
  },
];

const MODEL_IMAGES = [
  {
    src: "https://images.unsplash.com/photo-1530497610245-94d3c16cda28?w=1200&q=80&auto=format&fit=max",
    alt: "MRI brain scan imagery on a clinical display",
    title: "Signals in, risk out",
    subtitle: "Windowed vital features",
  },
  {
    src: "https://images.unsplash.com/photo-1581595220892-b0739db3ba8c?w=1200&q=80&auto=format&fit=max",
    alt: "Patient monitor displaying vital signs in a hospital room",
    title: "Four core vitals",
    subtitle: "HR, SpO2, BP, temperature",
  },
  {
    src: "https://images.unsplash.com/photo-1504439468489-c8920d796a29?w=1200&q=80&auto=format&fit=max",
    alt: "ECG waveform trace of a heartbeat on a dark screen",
    title: "Rolling four-hour window",
    subtitle: "Counts, deltas, slopes",
  },
  {
    src: "https://images.unsplash.com/photo-1579684385127-1ef15d508118?w=1200&q=80&auto=format&fit=max",
    alt: "Clinician reviewing patient data on a tablet",
    title: "Class-weighted LightGBM",
    subtitle: "Held-out AUROC 0.80",
  },
  {
    src: "https://images.unsplash.com/photo-1582719471384-894fbb16e074?w=1200&q=80&auto=format&fit=max",
    alt: "Researcher working with laboratory samples",
    title: "Real-data path",
    subtitle: "VitalDB, MIMIC-IV, CinC",
  },
  {
    src: "https://images.unsplash.com/photo-1538108149393-fbbd81895907?w=1200&q=80&auto=format&fit=max",
    alt: "Empty hospital ward beds ready for patients",
    title: "Patient-level splits",
    subtitle: "70 / 15 / 15, no leakage",
  },
  {
    src: "https://images.unsplash.com/photo-1551076805-e1869033e561?w=1200&q=80&auto=format&fit=max",
    alt: "Surgical team collaborating in an operating theatre",
    title: "One-step ESI bound",
    subtitle: "Clinician confirms, every time",
  },
  {
    src: "https://images.unsplash.com/photo-1576091160399-112ba8d25d1d?w=1200&q=80&auto=format&fit=max",
    alt: "Stethoscope resting on a medical chart",
    title: "Pinned provenance",
    subtitle: "Dataset + schema hashes",
  },
  {
    src: "https://images.unsplash.com/photo-1516549655169-df83a0774514?w=1200&q=80&auto=format&fit=max",
    alt: "Hospital corridor with medical equipment",
    title: "Abstain on low history",
    subtitle: "No score, never a false safe",
  },
  {
    src: "https://images.unsplash.com/photo-1587854692152-cbe660dbde88?w=1200&q=80&auto=format&fit=max",
    alt: "Doctor walking through a bright hospital hallway",
    title: "Append-only audit",
    subtitle: "Same-transaction writes",
  },
];

const SAFETY_CARDS = [
  {
    id: 1,
    tag: "Bounds",
    title: "One-step bound",
    icon: ShieldCheck,
    body: "A confirmed recommendation moves ESI by at most one category. Larger escalations require an explicit clinician override, each with a mandatory rationale.",
  },
  {
    id: 2,
    tag: "Outputs",
    title: "Honest outputs",
    icon: Activity,
    body: "If inference fails, the prior score is kept but marked STALE. Low-confidence scores are badged. Explanations are deterministic, structured templates — no generative text in the clinical path.",
  },
  {
    id: 3,
    tag: "Audit",
    title: "Append-only audit",
    icon: FileText,
    body: "Every decision and pipeline event lands in an audit trail the application cannot edit or delete. If the audit write fails, the whole action rolls back.",
  },
];

export default function MedLanding() {
  const [open, setOpen] = useState(false);
  const [scrolled, setScrolled] = useState(false);

  useEffect(() => {
    const onScroll = () => setScrolled(window.scrollY > 60);
    onScroll();
    window.addEventListener("scroll", onScroll, { passive: true });
    return () => window.removeEventListener("scroll", onScroll);
  }, []);

  return (
    <div
      className="relative flex flex-col uppercase tracking-widest font-semibold text-black"
      style={{ fontFamily: "'Inter', sans-serif" }}
    >
      <header
        className={`fixed inset-x-0 top-0 z-40 transition-colors duration-300 ${
          scrolled ? "bg-white/85 backdrop-blur-md border-b border-black/5" : ""
        }`}
      >
        <nav className="flex items-center justify-between px-5 sm:px-8 md:px-12 pt-5 md:pt-6 pb-4">
          <MotionLink
            to="/"
            custom={0}
            variants={fadeDown}
            initial="hidden"
            animate="show"
            className="w-8 h-8 rounded-full border-2 flex items-center justify-center"
            style={{ borderColor: ACCENT }}
            aria-label="MediQueue home"
          >
            <span className="w-[10px] h-[10px] rounded-full" style={{ backgroundColor: ACCENT }} />
          </MotionLink>

          <div className="hidden md:flex items-center gap-10">
            {NAV_LINKS.map((link, idx) => (
              <motion.a
                key={link.label}
                href={link.href}
                custom={idx + 1}
                variants={fadeDown}
                initial="hidden"
                animate="show"
                className="text-sm tracking-widest hover:opacity-70 transition-opacity"
              >
                {link.label}
              </motion.a>
            ))}
          </div>

          <motion.button
            custom={5}
            variants={fadeDown}
            initial="hidden"
            animate="show"
            onClick={() => setOpen(true)}
            className="w-9 h-9 rounded-full bg-black flex flex-col items-center justify-center gap-[3px]"
            aria-label="Open menu"
          >
            <span className="w-4 h-[2px] bg-white" />
            <span className="w-4 h-[2px] bg-white" />
            <span className="w-4 h-[2px] bg-white" />
          </motion.button>
        </nav>
      </header>

      {open && (
        <div className="fixed inset-0 z-50 bg-white flex flex-col uppercase tracking-widest font-semibold text-black">
          <div className="px-5 sm:px-8 md:px-12 pt-5 md:pt-6 flex items-center justify-between">
            <Link to="/" className="w-8 h-8 rounded-full border-2 flex items-center justify-center" style={{ borderColor: ACCENT }} aria-label="MediQueue home">
              <span className="w-[10px] h-[10px] rounded-full" style={{ backgroundColor: ACCENT }} />
            </Link>
            <button
              onClick={() => setOpen(false)}
              className="w-9 h-9 rounded-full bg-black flex items-center justify-center"
              aria-label="Close menu"
            >
              <X className="w-5 h-5 text-white" />
            </button>
          </div>
          <nav className="flex flex-col items-center mt-16 gap-8 text-3xl">
            {NAV_LINKS.map((link) => (
              <a key={link.label} href={link.href} onClick={() => setOpen(false)}>
                {link.label}
              </a>
            ))}
          </nav>
          <div className="mt-auto px-5 sm:px-8 md:px-12 pb-8">
            <Link
              to="/login"
              className="inline-flex items-center gap-2 text-xl"
              style={{ color: ACCENT }}
              onClick={() => setOpen(false)}
            >
              Open Dashboard <ArrowUpRight className="w-5 h-5" />
            </Link>
          </div>
        </div>
      )}

      {/* hero */}
      <section className="relative min-h-screen flex flex-col">
        <video
          className="absolute inset-0 w-full h-full object-cover"
          src={VIDEO_URL}
          autoPlay
          muted
          loop
          playsInline
        />
        <div className="absolute inset-0 bg-white/40" aria-hidden="true" />

        <main className="relative z-30 flex-1 flex flex-col pt-20">
          <section className="flex-1 flex items-center justify-end px-5 sm:px-8 md:px-12 py-8 md:py-0">
            <div className="flex flex-row gap-5 sm:gap-8 md:gap-10 text-right">
              {STATS.map((s, i) => (
                <motion.div
                  key={i}
                  custom={2 + i}
                  variants={fadeUp}
                  initial="hidden"
                  animate="show"
                  className="flex flex-col items-end"
                >
                  <div className="flex items-start gap-1">
                    {s.plus && (
                      <span className="text-[0.5em] leading-none" style={{ color: ACCENT }}>
                        +
                      </span>
                    )}
                    <span
                      className="text-black leading-none"
                      style={{ fontSize: "clamp(1.5rem,5vw,3.5rem)" }}
                    >
                      {s.n}
                    </span>
                  </div>
                  <p className="mt-1 text-[10px] sm:text-xs md:text-sm whitespace-pre-line leading-tight tracking-widest">
                    {s.a}
                  </p>
                </motion.div>
              ))}
            </div>
          </section>

          <section className="px-5 sm:px-8 md:px-12 pb-8 md:pb-12 flex flex-col gap-6 md:gap-12">
            <div className="flex items-center justify-between gap-4">
              <motion.p
                custom={5}
                variants={fadeUp}
                initial="hidden"
                animate="show"
                className="text-[10px] sm:text-xs md:text-sm tracking-widest max-w-[130px] sm:max-w-[160px] md:max-w-xs leading-tight"
              >
                Watching Every
                <br />
                Vital Sign In The
                <br />
                Waiting Room
              </motion.p>
              <MotionLink
                to="/login"
                custom={6}
                variants={fadeUp}
                initial="hidden"
                animate="show"
                className="inline-flex items-center gap-2 whitespace-nowrap text-base sm:text-xl md:text-2xl"
                style={{ color: ACCENT }}
              >
                Open Dashboard <ArrowUpRight className="w-[18px] h-[18px] sm:w-[22px] sm:h-[22px]" />
              </MotionLink>
            </div>

            <div className="flex items-end justify-between gap-3 sm:gap-4">
              <motion.div
                custom={7}
                variants={fadeUp}
                initial="hidden"
                animate="show"
                className="w-[120px] sm:w-[180px] md:w-[280px] shrink-0"
              >
                <p className="text-[9px] sm:text-xs md:text-sm tracking-widest text-left md:text-right leading-tight">
                  AI-Powered Early Warning And Dynamic Triage Built Around Four Core Vitals And A
                  Rolling Four-Hour Window
                </p>
              </motion.div>
              <div className="flex flex-col items-end text-right">
                {headingWords.map((w, i) => (
                  <div key={w} className="overflow-hidden">
                    <motion.span
                      initial={{ y: "110%" }}
                      animate={{ y: 0 }}
                      transition={{ delay: 0.4 + i * 0.14, duration: 0.7, ease: EASE }}
                      className="block leading-[0.88]"
                      style={{ fontSize: "clamp(2rem,9vw,9rem)" }}
                    >
                      {w}
                    </motion.span>
                  </div>
                ))}
              </div>
            </div>
          </section>
        </main>
      </section>

      {/* Platform tab — scroll-expanding media */}
      <div id="platform" className="scroll-mt-16 normal-case tracking-normal">
        <ScrollExpandMedia
          mediaType="image"
          mediaSrc="/platform-overview.gif"
          bgImageSrc={BG_IMAGE}
          title="Platform Overview"
          date="AI ED Early Warning"
          scrollToExpand="Scroll To Expand"
          textBlend
        >
          <div className="max-w-3xl mx-auto text-center text-black normal-case tracking-normal">
            <span className="text-xs font-bold uppercase tracking-widest" style={{ color: ACCENT }}>
              01 — Platform
            </span>
            <h2 className="mt-4 text-[clamp(1.5rem,4vw,2.6rem)] leading-tight font-semibold text-black">
              One pipeline, from raw vitals to an audited clinical decision
            </h2>
            <p className="mt-5 text-sm leading-relaxed text-black/70">
              Heart rate, SpO2, blood pressure and temperature stream in over a rolling four-hour
              window. Strict validation rejects ambiguous values, the model scores deterioration
              risk, and every recommendation stays bounded and clinician-confirmed. Scroll to
              expand the view.
            </p>
          </div>
        </ScrollExpandMedia>
      </div>

      {/* Pipeline tab — radial orbital timeline */}
      <section
        id="pipeline"
        className="relative scroll-mt-16 bg-[#060607] text-white px-5 sm:px-8 md:px-12 py-20 md:py-28 normal-case tracking-normal"
      >
        <motion.div
          initial={{ opacity: 0, y: 28 }}
          whileInView={{ opacity: 1, y: 0 }}
          viewport={{ once: true, margin: "-60px" }}
          transition={{ duration: 0.6, ease: EASE }}
          className="max-w-6xl mx-auto"
        >
          <div className="flex items-center gap-4">
            <span className="text-xs font-bold uppercase tracking-widest" style={{ color: ACCENT }}>
              02
            </span>
            <span className="text-[10px] sm:text-xs uppercase tracking-widest opacity-60">
              Pipeline
            </span>
            <span className="h-px flex-1 bg-white/15" />
          </div>
          <h2 className="mt-6 text-[clamp(1.5rem,4.2vw,2.9rem)] leading-[1.02] font-semibold max-w-3xl uppercase tracking-widest">
            Eight stages, every reading, fully audited
          </h2>
          <div className="mt-10 md:mt-14">
            <RadialOrbitalTimeline data={PIPELINE} centerTitle="Pipeline" centerSubtitle="Live" />
          </div>
        </motion.div>
      </section>

      {/* Safety tab — flip cards: title on front, description on back */}
      <section
        id="safety"
        className="relative scroll-mt-16 bg-[#F4EFFC] text-black px-5 sm:px-8 md:px-12 py-20 md:py-28 normal-case tracking-normal"
      >
        <motion.div
          initial={{ opacity: 0, y: 28 }}
          whileInView={{ opacity: 1, y: 0 }}
          viewport={{ once: true, margin: "-60px" }}
          transition={{ duration: 0.6, ease: EASE }}
          className="max-w-6xl mx-auto"
        >
          <div className="flex items-center gap-4">
            <span className="text-xs font-bold uppercase tracking-widest" style={{ color: ACCENT }}>
              03
            </span>
            <span className="text-[10px] sm:text-xs uppercase tracking-widest text-black/50">
              Safety
            </span>
            <span className="h-px flex-1 bg-black/10" />
          </div>
          <h2 className="mt-6 text-[clamp(1.5rem,4.2vw,2.9rem)] leading-[1.02] font-semibold max-w-3xl uppercase tracking-widest">
            Human in the loop — always
          </h2>
          <p className="mt-4 text-[10px] sm:text-xs uppercase tracking-widest text-black/40">
            Tap a card to flip it
          </p>
          <div className="mt-10 md:mt-14 flex flex-wrap justify-center gap-8 md:gap-10">
            {SAFETY_CARDS.map((card, i) => (
              <TiltedCard
                key={card.id}
                captionText={card.title}
                containerWidth={280}
                containerHeight={320}
                imageWidth={280}
                imageHeight={320}
                rotateAmplitude={12}
                glare={0.45}
                shadow={0.6}
                introDelay={i * 120}
                style={{ "--tc-shadow-color": "rgba(94, 14, 215, 0.32)" }}
                backContent={
                  <div className="flex h-full w-full flex-col justify-between border border-black/10 bg-white p-6">
                    <p className="text-sm sm:text-[15px] leading-[1.7] text-black/80">{card.body}</p>
                    <p className="text-[10px] uppercase tracking-widest text-black/40">
                      Tap to flip back
                    </p>
                  </div>
                }
              >
                <div className="flex h-full w-full flex-col justify-between border border-black/10 bg-white p-6">
                  <div className="flex items-center justify-between">
                    <span
                      className="text-[10px] font-bold uppercase tracking-widest"
                      style={{ color: ACCENT }}
                    >
                      {card.tag}
                    </span>
                    <card.icon className="w-4 h-4" style={{ color: ACCENT }} />
                  </div>
                  <h3 className="text-sm uppercase tracking-widest font-semibold leading-snug text-black">
                    {card.title}
                  </h3>
                  <p className="text-[10px] uppercase tracking-widest text-black/40">
                    Tap to flip
                  </p>
                </div>
              </TiltedCard>
            ))}
          </div>
        </motion.div>
      </section>

      {/* Model tab — WebGL flex carousel of clinical imagery */}
      <section
        id="model"
        className="relative scroll-mt-16 bg-[#060607] text-white px-5 sm:px-8 md:px-12 py-20 md:py-28 normal-case tracking-normal"
      >
        <motion.div
          initial={{ opacity: 0, y: 28 }}
          whileInView={{ opacity: 1, y: 0 }}
          viewport={{ once: true, margin: "-60px" }}
          transition={{ duration: 0.6, ease: EASE }}
          className="max-w-6xl mx-auto"
        >
          <div className="flex items-center gap-4">
            <span className="text-xs font-bold uppercase tracking-widest" style={{ color: ACCENT }}>
              04
            </span>
            <span className="text-[10px] sm:text-xs uppercase tracking-widest opacity-60">
              Model
            </span>
            <span className="h-px flex-1 bg-white/15" />
          </div>
          <h2 className="mt-6 text-[clamp(1.5rem,4.2vw,2.9rem)] leading-[1.02] font-semibold max-w-3xl uppercase tracking-widest">
            Gradient boosting with pinned provenance
          </h2>
          <div className="mt-10 md:mt-14 w-full h-[480px] sm:h-[560px]">
            <FlexCarousel
              items={MODEL_IMAGES}
              preset="liquid"
              intro="rise"
              cardHeight={0.5}
              gap={12}
              focusOnClick
              autoplay
              interval={4}
              captions
            />
          </div>
        </motion.div>
      </section>

      {/* footer CTA */}
      <section className="bg-white text-black px-5 sm:px-8 md:px-12 py-16 md:py-20">
        <div className="max-w-6xl mx-auto flex flex-col md:flex-row md:items-end justify-between gap-8">
          <div>
            <p className="text-[10px] sm:text-xs opacity-60">Ready when you are</p>
            <h2 className="mt-3 text-[clamp(1.4rem,3.5vw,2.4rem)] leading-tight max-w-xl">
              See the queue, the alerts and the explanations for yourself
            </h2>
          </div>
          <MotionLink
            to="/login"
            className="inline-flex items-center gap-2 whitespace-nowrap text-base sm:text-xl md:text-2xl"
            style={{ color: ACCENT }}
          >
            Open Dashboard <ArrowUpRight className="w-[18px] h-[18px] sm:w-[22px] sm:h-[22px]" />
          </MotionLink>
        </div>
      </section>

      <footer className="bg-[#060607] text-white/50 px-5 sm:px-8 md:px-12 py-6">
        <div className="max-w-6xl mx-auto flex flex-col sm:flex-row items-start sm:items-center justify-between gap-3 text-[9px] sm:text-[10px] uppercase tracking-widest">
          <span>MediQueue — AI ED Early Warning &amp; Dynamic Triage</span>
          <span>Decision support only — not a medical device · Apache-2.0</span>
        </div>
      </footer>
    </div>
  );
}
