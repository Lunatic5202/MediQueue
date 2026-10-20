import { useCallback, useEffect, useRef, useState } from "react";
import { motion } from "framer-motion";
import { ChevronLeft, ChevronRight } from "lucide-react";
import { cn } from "@/lib/utils";

const EASE = [0.22, 1, 0.36, 1];
const GAP = 18;

/**
 * SkewedCarousel — clean-room implementation of the React Bits Pro
 * "Skewed Carousel" API (cards tilt as they slide), built with framer-motion.
 * Adapted for this project: text cards via renderCard instead of images.
 */
export default function SkewedCarousel({
  items = [],
  initialIndex = 0,
  cardWidth = 200,
  aspectRatio = "3 / 4",
  rotation = 60,
  inactiveScale = 0.85,
  perspective = 800,
  borderRadius = 8,
  titleBlur = 2,
  speed = 1,
  showTitles = true,
  showControls = true,
  showDots = true,
  loop = false,
  autoplay = false,
  autoplayDelay = 3000,
  enableDrag = true,
  enableKeyboard = true,
  accent = "#5E0ED7",
  renderCard,
  className,
  onIndexChange,
}) {
  const count = items.length;
  const [index, setIndex] = useState(() =>
    Math.max(0, Math.min(initialIndex, count - 1)),
  );
  const [paused, setPaused] = useState(false);
  const draggingRef = useRef(false);

  const step = cardWidth + GAP;

  const [rw, rh] = String(aspectRatio)
    .split("/")
    .map((v) => parseFloat(v));
  const ratio = rw > 0 && rh > 0 ? rh / rw : 4 / 3;
  const height = Math.round(cardWidth * ratio);

  const go = useCallback(
    (next) => {
      setIndex((prev) => {
        let n = next;
        if (n < 0) n = loop ? count - 1 : 0;
        if (n > count - 1) n = loop ? 0 : count - 1;
        return n;
      });
    },
    [loop, count],
  );

  const next = useCallback(() => go(index + 1), [go, index]);
  const prev = useCallback(() => go(index - 1), [go, index]);

  useEffect(() => {
    onIndexChange?.(index);
  }, [index, onIndexChange]);

  useEffect(() => {
    if (!autoplay || count === 0 || paused) return undefined;
    const id = setInterval(() => {
      setIndex((i) => {
        if (i >= count - 1) return loop ? 0 : i;
        return i + 1;
      });
    }, autoplayDelay);
    return () => clearInterval(id);
  }, [autoplay, autoplayDelay, loop, count, paused, index]);

  const onKeyDown = (e) => {
    if (!enableKeyboard) return;
    if (e.key === "ArrowLeft") {
      e.preventDefault();
      prev();
    } else if (e.key === "ArrowRight") {
      e.preventDefault();
      next();
    }
  };

  return (
    <div
      className={cn("relative select-none", className)}
      style={{ perspective: `${perspective}px` }}
      tabIndex={enableKeyboard ? 0 : -1}
      onKeyDown={onKeyDown}
      onPointerEnter={() => setPaused(true)}
      onPointerLeave={() => setPaused(false)}
      role="region"
      aria-roledescription="carousel"
    >
      <motion.div
        className="relative w-full"
        style={{ height, touchAction: "pan-y", transformStyle: "preserve-3d" }}
        drag={enableDrag ? "x" : false}
        dragConstraints={{ left: 0, right: 0 }}
        dragElastic={0.1}
        onDragStart={() => {
          draggingRef.current = true;
          setPaused(true);
        }}
        onDragEnd={(_, info) => {
          draggingRef.current = false;
          setPaused(false);
          const threshold = 40;
          if (info.offset.x < -threshold) next();
          else if (info.offset.x > threshold) prev();
        }}
      >
        {items.map((item, i) => {
          const offset = i - index;
          const dist = Math.abs(offset);
          return (
            <div
              key={item.id ?? i}
              className="absolute top-0"
              style={{ left: "50%", marginLeft: -cardWidth / 2, zIndex: 100 - dist }}
              aria-hidden={i !== index}
            >
              <motion.div
                initial={false}
                animate={{
                  x: offset * step,
                  rotateY: offset * -rotation,
                  scale: i === index ? 1 : inactiveScale,
                }}
                transition={{ duration: 0.5 * speed, ease: EASE }}
                style={{ width: cardWidth, height }}
              >
                {renderCard ? (
                  renderCard(item, i === index)
                ) : (
                  <div
                    className="flex h-full w-full items-center justify-center border border-black/10 bg-white text-xs"
                    style={{ borderRadius }}
                  >
                    {item.title}
                  </div>
                )}
              </motion.div>
              {showTitles && item.title && (
                <p
                  className="mt-3 text-center text-[10px] uppercase tracking-widest transition-[filter,opacity] duration-300"
                  style={{
                    width: cardWidth,
                    filter: i === index ? "none" : `blur(${titleBlur}px)`,
                    opacity: i === index ? 1 : 0.45,
                  }}
                >
                  {item.title}
                </p>
              )}
            </div>
          );
        })}
      </motion.div>

      {showControls && count > 1 && (
        <>
          <button
            type="button"
            onClick={prev}
            aria-label="Previous slide"
            className="absolute left-0 top-1/2 z-[110] flex h-10 w-10 -translate-y-1/2 items-center justify-center rounded-full border border-black/10 bg-white transition-colors hover:bg-black/5 sm:-left-4"
          >
            <ChevronLeft className="h-5 w-5 text-black" />
          </button>
          <button
            type="button"
            onClick={next}
            aria-label="Next slide"
            className="absolute right-0 top-1/2 z-[110] flex h-10 w-10 -translate-y-1/2 items-center justify-center rounded-full border border-black/10 bg-white transition-colors hover:bg-black/5 sm:-right-4"
          >
            <ChevronRight className="h-5 w-5 text-black" />
          </button>
        </>
      )}

      {showDots && count > 1 && (
        <div className="mt-8 flex justify-center gap-2">
          {items.map((item, i) => (
            <button
              key={item.id ?? i}
              type="button"
              onClick={() => go(i)}
              aria-label={`Go to slide ${i + 1}`}
              aria-current={i === index}
              className={cn(
                "h-1.5 rounded-full transition-all duration-300",
                i === index ? "w-5" : "w-1.5 hover:opacity-70",
              )}
              style={{
                backgroundColor: i === index ? accent : "rgba(0,0,0,0.18)",
              }}
            />
          ))}
        </div>
      )}
    </div>
  );
}
