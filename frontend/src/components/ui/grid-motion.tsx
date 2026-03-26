"use client";

import { useEffect, useRef, ReactNode, useState } from "react";

interface GridMotionProps {
  items?: (string | ReactNode)[];
  gradientColor?: string;
  className?: string;
}

export function GridMotion({
  items = [],
  gradientColor = "black",
  className = "",
}: GridMotionProps) {
  const gridRef = useRef<HTMLDivElement>(null);
  const rowRefs = useRef<(HTMLDivElement | null)[]>([]);
  const mouseXRef = useRef(0);
  const [isMobile, setIsMobile] = useState(false);

  useEffect(() => {
    const checkMobile = () => {
      setIsMobile(window.innerWidth < 768);
      mouseXRef.current = window.innerWidth / 2;
    };

    checkMobile();
    window.addEventListener("resize", checkMobile);

    return () => window.removeEventListener("resize", checkMobile);
  }, []);

  const totalItems = isMobile ? 12 : 28;
  const rows = 3;
  const cols = 4;

  const defaultItems = Array.from(
    { length: totalItems },
    (_, index) => `Item ${index + 1}`,
  );
  const combinedItems =
    items.length > 0 ? items.slice(0, totalItems) : defaultItems;

  useEffect(() => {
    if (isMobile) return;

    const handleMouseMove = (e: MouseEvent) => {
      mouseXRef.current = e.clientX;
    };

    const handleTouchMove = (e: TouchEvent) => {
      if (e.touches.length > 0) {
        mouseXRef.current = e.touches[0].clientX;
      }
    };

    const updateMotion = () => {
      const maxMoveAmount = isMobile ? 150 : 300;

      rowRefs.current.forEach((row, index) => {
        if (row) {
          const direction = index % 2 === 0 ? 1 : -1;
          const moveAmount =
            ((mouseXRef.current / window.innerWidth) * maxMoveAmount -
              maxMoveAmount / 2) *
            direction;

          if (row.style) {
            row.style.transform = `translateX(${moveAmount}px)`;
          }
        }
      });

      requestAnimationFrame(updateMotion);
    };

    const animationId = requestAnimationFrame(updateMotion);
    window.addEventListener("mousemove", handleMouseMove);
    window.addEventListener("touchmove", handleTouchMove);

    return () => {
      window.removeEventListener("mousemove", handleMouseMove);
      window.removeEventListener("touchmove", handleTouchMove);
      cancelAnimationFrame(animationId);
    };
  }, [isMobile]);

  return (
    <div
      className={`h-screen w-full overflow-hidden ${className}`}
      ref={gridRef}
    >
      <section
        className="relative flex h-full w-full items-center justify-center overflow-hidden"
        style={{
          background: `radial-gradient(circle, ${gradientColor} 0%, transparent 100%)`,
        }}
      >
        <div
          className="relative flex flex-col gap-3 md:gap-4 -rotate-12 md:-rotate-12"
          style={{
            width: isMobile ? "140vw" : "120vw",
          }}
        >
          {[...Array(rows)].map((_, rowIndex) => (
            <div
              key={rowIndex}
              className="grid gap-3 md:gap-4 will-change-transform transition-transform duration-700 ease-out"
              style={{
                gridTemplateColumns: `repeat(${cols}, minmax(20rem, 1fr))`,
              }}
              ref={(el: any) => (rowRefs.current[rowIndex] = el)}
            >
              {[...Array(cols)].map((_, itemIndex) => {
                const content = combinedItems[rowIndex * cols + itemIndex];
                return (
                  <div key={itemIndex} className="relative aspect-square ">
                    <div className="relative h-full w-full overflow-hidden rounded-lg md:rounded-xl flex items-center justify-center bg-gray-100 text-gray-800 text-sm md:text-base font-medium shadow-md">
                      {typeof content === "string" &&
                      content.startsWith("http") ? (
                        <div
                          className="absolute inset-0 bg-cover bg-center"
                          style={{
                            backgroundImage: `url(${content})`,
                          }}
                        />
                      ) : (
                        <div className="h-full w-full flex items-center justify-center p-2">
                          {content}
                        </div>
                      )}
                    </div>
                  </div>
                );
              })}
            </div>
          ))}
        </div>
      </section>
    </div>
  );
}

// Demo usage
export default function App() {
  return (
    <div className="w-full h-screen bg-gray-900">
      <GridMotion gradientColor="rgba(59, 130, 246, 0.15)" />
    </div>
  );
}
