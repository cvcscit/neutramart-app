"use client";

import { useRef } from "react";
import {
  motion,
  useScroll,
  useTransform,
  useSpring,
  MotionValue,
} from "framer-motion";
import demo1 from "@/assets/images/upload-your-food.png";
import demo2 from "@/assets/images/ai-work-for-you.png";
import demo3 from "@/assets/images/track-data.png";

// ─── Data ─────────────────────────────────────────────────────────────────────

interface Section {
  id: number;
  step: string;
  title: string;
  description: string;
  imageUrl: string;
  reverse?: boolean;
}

const sections: Section[] = [
  {
    id: 1,
    step: "01",
    title: "Upload your food",
    description:
      "Start by uploading whatever food you want to document. Multiple files welcome.",
    imageUrl: demo1,
    reverse: false,
  },
  {
    id: 2,
    step: "02",
    title: "Let the AI work for you",
    description:
      "The AI analyzes each dish and produces a full nutritional breakdown automatically.",
    imageUrl: demo2,
    reverse: true,
  },
  {
    id: 3,
    step: "03",
    title: "Track all your data",
    description:
      "Add food to your Profile and maintain a full history of your caloric intake.",
    imageUrl: demo3,
    reverse: false,
  },
];

// ─── Spring helper ─────────────────────────────────────────────────────────────

function useSmooth(
  v: MotionValue<number>,
  s = 80,
  d = 22,
): MotionValue<number> {
  return useSpring(v, { stiffness: s, damping: d, restDelta: 0.001 });
}

// ─── Masked word-by-word title reveal ─────────────────────────────────────────
// Each word is inside overflow:hidden and translates up from 110% → 0%
// giving that classic awwwards "curtain lift" effect.

function MaskedTitle({
  text,
  progress,
  className = "",
}: {
  text: string;
  progress: MotionValue<number>;
  className?: string;
}) {
  const words = text.split(" ");
  return (
    <span className={`flex flex-wrap gap-x-[0.3em] ${className}`}>
      {words.map((word, i) => {
        const start = 0.04 + i * 0.08;
        const end = start + 0.22;
        // Hooks inside map is normally illegal — but this is NOT inside a
        // component function. We handle this by calling MaskedTitle only once
        // per render, making it effectively a custom hook-like component.
        // To stay 100% safe we inline the transforms with stable indices.
        // eslint-disable-next-line react-hooks/rules-of-hooks
        const y = useTransform(progress, [start, end], ["108%", "0%"]);
        // eslint-disable-next-line react-hooks/rules-of-hooks
        const opacity = useTransform(progress, [start, start + 0.08], [0, 1]);
        return (
          <span
            key={i}
            style={{ overflow: "hidden", display: "block", lineHeight: 1.15 }}
          >
            <motion.span style={{ y, opacity, display: "block" }}>
              {word}
            </motion.span>
          </span>
        );
      })}
    </span>
  );
}

// ─── Desktop Section ───────────────────────────────────────────────────────────
// Each section is a 220vh scroll container.
// A sticky inner catches at top:0 and drives all animation from scrollYProgress.

function DesktopSection({
  section,
  index,
}: {
  section: Section;
  index: number;
}) {
  const ref = useRef<HTMLDivElement>(null);

  const { scrollYProgress } = useScroll({
    target: ref,
    offset: ["start start", "end end"],
  });
  const sp = useSmooth(scrollYProgress, 90, 26);

  // ── Image clip-path reveal ─────────────────────────────────────────────────
  // The image wipes in from the correct side depending on reverse layout
  const imageClip = useTransform(
    sp,
    [0.05, 0.5],
    section.reverse
      ? ["inset(0 0% 0 100% round 14px)", "inset(0 0% 0 0% round 14px)"]
      : ["inset(0 100% 0 0% round 14px)", "inset(0 0% 0 0% round 14px)"],
  );

  // ── Foreground color wipe panel (sweeps in then exits opposite side) ───────
  const panelClip = useTransform(
    sp,
    [0.05, 0.48],
    section.reverse
      ? ["inset(0 0% 0 100% round 14px)", "inset(0 0% 0 0% round 14px)"]
      : ["inset(0 100% 0 0% round 14px)", "inset(0 0% 0 0% round 14px)"],
  );
  const panelExit = useTransform(
    sp,
    [0.48, 0.72],
    section.reverse ? ["0%", "-102%"] : ["0%", "102%"],
  );

  // ── Image inner parallax (image drifts subtly inside its clip box) ─────────
  const imageInnerY = useTransform(sp, [0, 1], ["6%", "-6%"]);

  // ── Ghost step number parallax ─────────────────────────────────────────────
  const ghostY = useTransform(sp, [0, 1], ["4%", "-18%"]);

  // ── Description fade-up ────────────────────────────────────────────────────
  const descOpacity = useTransform(sp, [0.38, 0.62], [0, 1]);
  const descY = useTransform(sp, [0.38, 0.62], [22, 0]);

  // ── Step label slide-in ────────────────────────────────────────────────────
  const stepOpacity = useTransform(sp, [0.0, 0.15], [0, 1]);
  const stepX = useTransform(sp, [0.0, 0.15], [-18, 0]);

  // ── Vertical progress line fills down ─────────────────────────────────────
  const lineScaleY = useTransform(sp, [0, 0.88], [0, 1]);

  // ── Section exit: everything shifts slightly off as next section loads ─────
  const sectionExit = useTransform(sp, [0.82, 1], [0, -30]);
  const sectionExitOpacity = useTransform(sp, [0.85, 1], [1, 0]);

  return (
    <div ref={ref} className="relative h-[220vh]">
      <div className="sticky top-0 h-screen overflow-hidden flex items-center">
        {/* Ghost step number */}
        <motion.div
          aria-hidden
          style={{ y: ghostY }}
          className={`
            pointer-events-none select-none absolute font-black
            text-[28vw] leading-none text-green-700/[0.15]
            ${section.reverse ? "-right-[4vw] top-[-8%]" : "-left-[4vw] top-[-8%]"}
          `}
        >
          {section.step}
        </motion.div>

        {/* Vertical progress line — right side */}
        <div
          className={`
            absolute top-[12%] bottom-[12%] w-[1px] bg-border z-100 hidden xl:block
            ${section.reverse ? "left-10" : "right-10"}
          `}
        >
          <motion.div
            style={{ scaleY: lineScaleY }}
            className="origin-top h-full w-full bg-foreground/50"
          />
        </div>

        {/* Main content row */}
        <motion.div
          style={{ y: sectionExit, opacity: sectionExitOpacity }}
          className={`
            w-full flex items-center justify-center
            gap-12 xl:gap-20 px-10 md:px-16 lg:px-24
            ${section.reverse ? "flex-row-reverse" : "flex-row"}
          `}
        >
          {/* ── Text column ── */}
          <div className="flex-1 max-w-[400px]">
            {/* Step label */}
            <motion.div
              style={{ opacity: stepOpacity, x: stepX }}
              className="flex items-center gap-3 mb-6"
            >
              <span className="text-[9px] font-bold tracking-[0.32em] uppercase text-muted-foreground">
                Step {section.step}
              </span>
              <motion.div
                style={{ scaleX: useTransform(sp, [0.08, 0.38], [0, 1]) }}
                className="origin-left w-20 h-px bg-foreground/20"
              />
            </motion.div>

            {/* Masked word-reveal title */}
            <MaskedTitle
              text={section.title}
              progress={sp}
              className="text-[2.4rem] lg:text-[3rem] xl:text-[3.6rem] font-semibold tracking-tight text-foreground mb-8"
            />

            {/* Description */}
            <motion.p
              style={{ opacity: descOpacity, y: descY }}
              className="text-base lg:text-lg text-muted-foreground leading-relaxed"
            >
              {section.description}
            </motion.p>
          </div>

          {/* ── Image column ── */}
          <div className="flex-1 flex justify-center max-w-[500px]">
            <div className="relative w-full aspect-[4/3]">
              {/* Color wipe panel */}
              <motion.div
                style={{ clipPath: panelClip, x: panelExit }}
                className="absolute inset-0 bg-white rounded-[14px] z-10 will-change-transform"
              />

              {/* Image itself */}
              <motion.div
                style={{ clipPath: imageClip }}
                className="absolute inset-0 rounded-[14px] overflow-hidden shadow-[0_30px_80px_-10px_rgba(0,0,0,0.25)] will-change-transform"
              >
                <motion.img
                  src={section.imageUrl}
                  alt={section.title}
                  style={{ y: imageInnerY }}
                  className="w-full absolute inset-0 h-[115%] -top-[7%] object-cover will-change-transform"
                />
              </motion.div>
            </div>
          </div>
        </motion.div>

        {/* Section divider */}
        {index < sections.length - 1 && (
          <motion.div
            style={{ scaleX: useTransform(sp, [0.75, 1], [0, 1]) }}
            className="absolute bottom-0 origin-left left-[8%] right-[8%] h-px lg:bg-border xl:bg-border"
          />
        )}
      </div>
    </div>
  );
}

// ─── Desktop Wrapper ───────────────────────────────────────────────────────────

function DesktopParallax() {
  const wrapperRef = useRef<HTMLDivElement>(null);
  const { scrollYProgress } = useScroll({
    target: wrapperRef,
    offset: ["start start", "end end"],
  });
  const smoothTotal = useSmooth(scrollYProgress, 100, 30);
  const barScaleX = useTransform(smoothTotal, [0, 1], [0, 1]);

  return (
    <div ref={wrapperRef} className="hidden md:block relative">
      {/* Global progress bar */}
      <div className="fixed top-0 left-0 right-0 z-[100] h-[1.5px] bg-border pointer-events-none">
        <motion.div
          style={{ scaleX: barScaleX }}
          className="origin-left h-full bg-foreground/80"
        />
      </div>

      {sections.map((section, index) => (
        <DesktopSection key={section.id} section={section} index={index} />
      ))}
    </div>
  );
}

// ─── Mobile Section ────────────────────────────────────────────────────────────

function MobileSection({ section }: { section: Section }) {
  const ref = useRef<HTMLDivElement>(null);
  const { scrollYProgress } = useScroll({
    target: ref,
    offset: ["start end", "center center"],
  });
  const sp = useSmooth(scrollYProgress, 55, 16);

  const imageClip = useTransform(
    sp,
    [0.05, 0.65],
    ["inset(0 100% 0 0% round 10px)", "inset(0 0% 0 0% round 10px)"],
  );
  const panelClip = useTransform(
    sp,
    [0.05, 0.62],
    ["inset(0 100% 0 0% round 10px)", "inset(0 0% 0 0% round 10px)"],
  );
  const panelExit = useTransform(sp, [0.62, 0.9], ["0%", "105%"]);

  const textOpacity = useTransform(sp, [0.04, 0.35], [0, 1]);
  const textY = useTransform(sp, [0.04, 0.35], [28, 0]);
  const descOpacity = useTransform(sp, [0.5, 0.85], [0, 1]);
  const descY = useTransform(sp, [0.5, 0.85], [16, 0]);

  return (
    <motion.div
      ref={ref}
      style={{ opacity: useTransform(sp, [0, 0.06], [0, 1]) }}
      className="flex flex-col gap-4 pb-10 border-b border-border last:border-none"
    >
      <div className="flex items-center gap-3">
        <span className="text-[9px] font-bold tracking-[0.35em] uppercase text-muted-foreground">
          Step {section.step}
        </span>
        <div className="h-px flex-1 bg-border" />
      </div>

      <motion.h3
        style={{ y: textY, opacity: textOpacity }}
        className="text-3xl font-semibold text-foreground tracking-tight"
      >
        {section.title}
      </motion.h3>

      {/* Image with wipe */}
      <div className="relative w-full aspect-[4/3]">
        <motion.div
          style={{ clipPath: panelClip, x: panelExit }}
          className="absolute inset-0 bg-white rounded-[10px] z-10 will-change-transform"
        />
        <motion.div
          style={{ clipPath: imageClip }}
          className="absolute inset-0 rounded-[10px] overflow-hidden shadow-xl will-change-transform"
        >
          <img
            src={section.imageUrl}
            alt={section.title}
            className="w-full h-full object-cover"
          />
        </motion.div>
      </div>

      <motion.p
        style={{ opacity: descOpacity, y: descY }}
        className="text-sm text-muted-foreground leading-relaxed"
      >
        {section.description}
      </motion.p>
    </motion.div>
  );
}

function MobileGrid() {
  return (
    <div className="md:hidden px-5 pt-12 pb-8 flex flex-col gap-10">
      {sections.map((section) => (
        <MobileSection key={section.id} section={section} />
      ))}
    </div>
  );
}

// ─── Export ────────────────────────────────────────────────────────────────────

export default function ParallaxSection() {
  return (
    <>
      <MobileGrid />
      <DesktopParallax />
    </>
  );
}
