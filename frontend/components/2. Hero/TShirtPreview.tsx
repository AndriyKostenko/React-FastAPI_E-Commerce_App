"use client";

import { useState } from "react";
import { TShirtPreviewProps } from "@/types/banner";
import { COLOR_MAP, SHIRT_PATH_BACK, SHIRT_PATH_FRONT } from "@/utils/constants";
import { placementZone, type ShirtSide } from "@/utils/printAreas";
import { resolveImageUrl } from "@/utils/resolveImageUrl";

const MIN_ZOOM = 0.5;
const MAX_ZOOM = 3;
const ZOOM_STEP = 0.1;

const COLLAR = {
  front: { band: "M 160,80 C 175,112 225,112 240,80", sheen: "M 163,83 C 178,110 222,110 237,83" },
  back: { band: "M 160,80 Q 200,68 240,80", sheen: "M 163,80 Q 200,71 237,80" },
} as const;

/**
 * How the print sits on the fabric (Strategy by garment colour). On a light
 * shirt the ink is absorbed, so white in the artwork shows the shirt through
 * (multiply). On a dark shirt the printer lays a white underbase first, so the
 * artwork shows as it is.
 */
const PRINT_BLEND: Readonly<Record<TShirtPreviewProps["color"], React.CSSProperties["mixBlendMode"]>> = {
  "bg-white": "multiply",
  "bg-black": "normal",
};

export default function TShirtPreview({ color, placement, designUrl, isGenerating = false }: TShirtPreviewProps) {
  const [zoom, setZoom] = useState(1);
  // The side the customer flipped to, remembered per placement: choosing a
  // new placement shows the side it prints on, without an effect to sync it.
  const [flipped, setFlipped] = useState<{ placement: string; side: ShirtSide } | null>(null);

  const zone = placementZone(placement);
  const side: ShirtSide = flipped?.placement === placement ? flipped.side : zone.side;
  const showsPrint = side === zone.side;
  const isBack = side === "back";
  const isBlack = color === "bg-black";
  const c = COLOR_MAP[color] ?? COLOR_MAP["bg-white"];
  const previewImageUrl = designUrl ? resolveImageUrl(designUrl) : "";
  const shirtPath = isBack ? SHIRT_PATH_BACK : SHIRT_PATH_FRONT;
  const collar = COLLAR[side];

  const flip = () => setFlipped({ placement, side: side === "front" ? "back" : "front" });

  return (
    <div className="relative w-full h-full flex flex-col">
      <div className="absolute top-2 right-2 z-10 flex rounded-full bg-white/60 border border-white/40 p-0.5 text-xs font-label-bold">
        {(["front", "back"] as const).map((option) => (
          <button
            key={option}
            type="button"
            onClick={option === side ? undefined : flip}
            aria-pressed={option === side}
            className={`px-3 py-1 rounded-full capitalize transition ${option === side ? "bg-primary text-on-primary" : "text-primary"}`}
          >
            {option}
          </button>
        ))}
      </div>

      <div className="flex-1 flex items-center justify-center overflow-auto">
        <div
          style={{
            transform: `scale(${zoom})`,
            transformOrigin: "center center",
            transition: "transform 0.2s ease-out",
          }}
        >
          <svg
            viewBox="-67 -80 534 640"
            xmlns="http://www.w3.org/2000/svg"
            className="w-full h-full scale-[1.5] origin-center"
            role="img"
            aria-label={`T-shirt ${side} preview${showsPrint ? `, print ${zone.widthIn} by ${zone.heightIn} inches` : ""}`}
          >
            <defs>
              <filter id="shirtShadow" x="-8%" y="-4%" width="116%" height="116%">
                <feDropShadow dx="0" dy="10" stdDeviation="14" floodColor="rgba(0,0,0,0.22)" />
              </filter>
              {/* A fine woven grain, laid over the shirt and the print alike so
                  the artwork reads as printed into the fabric, not pasted on. */}
              <filter id="fabricGrain" x="0" y="0" width="100%" height="100%">
                <feTurbulence type="fractalNoise" baseFrequency="0.9" numOctaves="2" seed="7" result="noise" />
                <feColorMatrix type="saturate" values="0" />
              </filter>
              {/* Soft folds: lighter down the middle, darker toward the sides. */}
              <linearGradient id="fabricFolds" x1="0" x2="1" y1="0" y2="0">
                <stop offset="0" stopColor="#000" stopOpacity="0.10" />
                <stop offset="0.3" stopColor="#000" stopOpacity="0" />
                <stop offset="0.5" stopColor="#fff" stopOpacity="0.06" />
                <stop offset="0.7" stopColor="#000" stopOpacity="0" />
                <stop offset="1" stopColor="#000" stopOpacity="0.12" />
              </linearGradient>
              <clipPath id="shirtClip">
                <path d={shirtPath} />
              </clipPath>
            </defs>

            <path d={shirtPath} fill={c.base} filter="url(#shirtShadow)" style={{ transition: "fill 0.45s ease" }} />

            <path d={collar.band} fill="none" stroke={c.collarBand} strokeWidth="9" strokeLinecap="round" />
            <path d={collar.sheen} fill="none" stroke={c.collarSheen} strokeWidth="2.5" strokeLinecap="round" opacity="0.8" />

            {isBack && (
              <rect
                x="193"
                y="76"
                width="14"
                height="20"
                fill={isBlack ? "rgba(255,255,255,0.10)" : "rgba(0,0,0,0.07)"}
                stroke={isBlack ? "rgba(255,255,255,0.05)" : "rgba(0,0,0,0.04)"}
                strokeWidth="1"
                rx="1.5"
              />
            )}

            <line x1="160" y1="80" x2="76" y2="70" stroke={c.seam} strokeWidth="1.5" />
            <line x1="240" y1="80" x2="324" y2="70" stroke={c.seam} strokeWidth="1.5" />
            <path d="M 44,202 L 6,188" fill="none" stroke={c.seam} strokeWidth="2" />
            <path d="M 356,202 L 394,188" fill="none" stroke={c.seam} strokeWidth="2" />

            {showsPrint && (
              <g clipPath="url(#shirtClip)">
                {/* The printable area, at its true size: a guide, faint enough to ignore. */}
                <rect
                  x={zone.x}
                  y={zone.y}
                  width={zone.w}
                  height={zone.h}
                  fill="none"
                  stroke={isBlack ? "rgba(255,255,255,0.25)" : "rgba(0,0,0,0.18)"}
                  strokeWidth="1.2"
                  strokeDasharray="6 5"
                  style={{ transition: "all 0.5s ease" }}
                />
                {previewImageUrl && (
                  <image
                    href={previewImageUrl}
                    x={zone.x}
                    y={zone.y}
                    width={zone.w}
                    height={zone.h}
                    preserveAspectRatio="xMidYMid meet"
                    style={{
                      mixBlendMode: PRINT_BLEND[color],
                      opacity: isGenerating ? 0.15 : 0.96,
                      transition: "opacity 0.55s ease, x 0.5s ease, y 0.5s ease, width 0.5s ease, height 0.5s ease",
                    }}
                  />
                )}
              </g>
            )}

            {/* Fabric over everything on the shirt, print included. */}
            <g clipPath="url(#shirtClip)" pointerEvents="none">
              <rect x="0" y="60" width="400" height="420" fill="url(#fabricFolds)" />
              <rect
                x="0"
                y="60"
                width="400"
                height="420"
                filter="url(#fabricGrain)"
                opacity={isBlack ? 0.07 : 0.1}
                style={{ mixBlendMode: isBlack ? "screen" : "multiply" }}
              />
            </g>

            {isGenerating && (
              <path d={shirtPath} fill={isBlack ? "rgba(255,255,255,0.08)" : "rgba(255,255,255,0.55)"} className="animate-pulse" />
            )}
          </svg>
        </div>
      </div>

      <p className="text-center text-xs text-secondary mt-1">
        {showsPrint
          ? `Print area: ${zone.widthIn} × ${zone.heightIn} in`
          : `Your print is on the ${zone.side}.`}
      </p>

      {/* Zoom controls stay inside the preview (not fixed to the screen). */}
      <div className="absolute bottom-6 left-0 right-0 z-10 flex justify-center pointer-events-none">
        <div className="glass-card p-2 flex justify-between items-center gap-2 pointer-events-auto">
          <div className="flex gap-1">
            <button
              type="button"
              onClick={() => setZoom((prev) => Math.max(prev - ZOOM_STEP, MIN_ZOOM))}
              disabled={zoom <= MIN_ZOOM}
              className="h-8 px-2 rounded-lg font-label-bold text-xs bg-white/60 text-primary border border-white/20 hover:bg-white/80 transition-all hover:scale-110 disabled:opacity-50 disabled:cursor-not-allowed"
              aria-label="Zoom out"
            >
              −
            </button>
            <span className="px-2 py-1.5 text-xs font-label-bold text-primary min-w-[40px] text-center">
              {Math.round(zoom * 100)}%
            </span>
            <button
              type="button"
              onClick={() => setZoom((prev) => Math.min(prev + ZOOM_STEP, MAX_ZOOM))}
              disabled={zoom >= MAX_ZOOM}
              className="h-8 px-2 rounded-lg font-label-bold text-xs bg-white/60 text-primary border border-white/20 hover:bg-white/80 transition-all hover:scale-110 disabled:opacity-50 disabled:cursor-not-allowed"
              aria-label="Zoom in"
            >
              +
            </button>
          </div>
          <button
            type="button"
            onClick={() => setZoom(1)}
            className="bg-brand-lime text-primary px-3 py-1 rounded-full font-label-bold text-xs hover:shadow-md transition-all active:scale-95"
          >
            Reset
          </button>
        </div>
      </div>
    </div>
  );
}
