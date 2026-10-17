"use client";

import { useState } from "react";
import { TShirtPreviewProps } from "@/types/banner";
import { GENERATION_COUNTDOWN_SECONDS, SIZE_MEASUREMENTS } from "@/utils/constants";
import ShirtMeasurements from "./ShirtMeasurements";
import { placementZone, type ShirtSide } from "@/utils/printAreas";
import { resolveImageUrl } from "@/utils/resolveImageUrl";
import {
  ARMHOLE_SEAMS,
  COLLAR,
  FOLDS,
  HEM_STITCHES,
  INNER_BACK_COLLAR,
  NECK_INSIDE,
  SHIRT_OUTLINE,
  SHIRT_PALETTES,
} from "@/utils/shirtShape";

const MIN_ZOOM = 0.5;
const MAX_ZOOM = 3;
const ZOOM_STEP = 0.1;

// Fitted to the shirt (x -4..404, y 62..480) and its measurements (the width
// line under the hem, the length line right of the sleeve), so the shirt fills
// the preview instead of sitting low in an oversized canvas.
const VIEW_BOX = "-40 44 500 480";

// The countdown ring: a circle of this radius, drawn as a stroke whose visible
// length is the share of time left.
const RING_RADIUS = 26;
const RING_LENGTH = 2 * Math.PI * RING_RADIUS;

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

export default function TShirtPreview({
  color,
  size,
  placement,
  designUrl,
  isGenerating = false,
  secondsLeft = null,
}: TShirtPreviewProps) {
  const [zoom, setZoom] = useState(1);
  // The side the customer flipped to, remembered per placement: choosing a
  // new placement shows the side it prints on, without an effect to sync it.
  const [flipped, setFlipped] = useState<{ placement: string; side: ShirtSide } | null>(null);

  const zone = placementZone(placement);
  const side: ShirtSide = flipped?.placement === placement ? flipped.side : zone.side;
  const showsPrint = side === zone.side;
  const isBack = side === "back";
  const isBlack = color === "bg-black";
  const palette = SHIRT_PALETTES[color] ?? SHIRT_PALETTES["bg-white"];
  const previewImageUrl = designUrl ? resolveImageUrl(designUrl) : "";
  const outline = SHIRT_OUTLINE[side];
  const collar = COLLAR[side];

  const flip = () => setFlipped({ placement, side: side === "front" ? "back" : "front" });

  return (
    <div className="relative w-full h-full flex flex-col">
      <div className="absolute top-0 right-0 z-10 flex rounded-full bg-white/60 border border-white/40 p-0.5 text-xs font-label-bold">
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

      <div className="relative flex-1 min-h-0 flex items-center justify-center overflow-hidden">
        <div
          className="h-full w-full flex items-center justify-center"
          style={{
            transform: `scale(${zoom})`,
            transformOrigin: "center center",
            transition: "transform 0.2s ease-out",
          }}
        >
          <svg
            viewBox={VIEW_BOX}
            xmlns="http://www.w3.org/2000/svg"
            className="h-full w-full max-h-full"
            preserveAspectRatio="xMidYMid meet"
            role="img"
            aria-label={`T-shirt ${side} preview${showsPrint ? `, print ${zone.widthIn} by ${zone.heightIn} inches` : ""}`}
          >
            <defs>
              <filter id="shirtShadow" x="-10%" y="-6%" width="120%" height="120%">
                <feDropShadow dx="0" dy="8" stdDeviation="10" floodColor="rgba(0,0,0,0.16)" />
              </filter>
              <filter id="foldBlur" x="-20%" y="-20%" width="140%" height="140%">
                <feGaussianBlur stdDeviation="6" />
              </filter>
              {/* A fine woven grain, laid over the shirt and the print alike so
                  the artwork reads as printed into the fabric, not pasted on. */}
              <filter id="fabricGrain" x="0" y="0" width="100%" height="100%">
                <feTurbulence type="fractalNoise" baseFrequency="0.9" numOctaves="2" seed="7" result="noise" />
                <feColorMatrix type="saturate" values="0" />
              </filter>
              {/* The body is rounder than the drawing: darker toward the sides. */}
              <linearGradient id="fabricRound" x1="0" x2="1" y1="0" y2="0">
                <stop offset="0" stopColor="#000" stopOpacity="0.09" />
                <stop offset="0.22" stopColor="#000" stopOpacity="0" />
                <stop offset="0.78" stopColor="#000" stopOpacity="0" />
                <stop offset="1" stopColor="#000" stopOpacity="0.10" />
              </linearGradient>
              {/* Light from above: the hem a touch darker than the chest. */}
              <linearGradient id="fabricLight" x1="0" x2="0" y1="0" y2="1">
                <stop offset="0" stopColor="#fff" stopOpacity="0.06" />
                <stop offset="0.6" stopColor="#000" stopOpacity="0" />
                <stop offset="1" stopColor="#000" stopOpacity="0.06" />
              </linearGradient>
              <clipPath id="shirtClip">
                <path d={outline} />
              </clipPath>
            </defs>

            <path
              d={outline}
              fill={palette.fabric}
              stroke={palette.edge}
              strokeWidth="1.2"
              strokeLinejoin="round"
              filter="url(#shirtShadow)"
              style={{ transition: "fill 0.45s ease" }}
            />

            {/* Folds, seams and stitching belong to the cloth: kept inside it. */}
            <g clipPath="url(#shirtClip)" pointerEvents="none">
              <g filter="url(#foldBlur)" opacity={palette.foldOpacity}>
                {FOLDS.map((fold) => (
                  <path key={fold.d} d={fold.d} fill="none" stroke={palette.fold} strokeWidth={fold.width} strokeLinecap="round" />
                ))}
              </g>
              {ARMHOLE_SEAMS.map((seam) => (
                <path key={seam} d={seam} fill="none" stroke={palette.seam} strokeWidth="1.4" />
              ))}
              {HEM_STITCHES.map((stitch) => (
                <path key={stitch} d={stitch} fill="none" stroke={palette.stitch} strokeWidth="0.9" strokeDasharray="3 2" />
              ))}
            </g>

            {/* Through the front neckline: the inside of the back and its collar band. */}
            {!isBack && (
              <>
                <path d={NECK_INSIDE} fill={palette.neckInside} />
                <path d={INNER_BACK_COLLAR} fill="none" stroke={palette.collarBand} strokeWidth="6" strokeLinecap="round" />
              </>
            )}
            <path d={collar.band} fill="none" stroke={palette.collarBand} strokeWidth="8" strokeLinecap="round" />
            <path d={collar.sheen} fill="none" stroke={palette.collarSheen} strokeWidth="2" strokeLinecap="round" opacity="0.8" />

            {isBack && (
              <rect
                x="193"
                y="74"
                width="14"
                height="18"
                fill={isBlack ? "rgba(255,255,255,0.10)" : "rgba(0,0,0,0.06)"}
                stroke={isBlack ? "rgba(255,255,255,0.05)" : "rgba(0,0,0,0.04)"}
                strokeWidth="1"
                rx="1.5"
              />
            )}

            {showsPrint && (
              <g clipPath="url(#shirtClip)">
                {/* The printable area, at its true size: a guide, faint enough to ignore. */}
                <rect
                  x={zone.x}
                  y={zone.y}
                  width={zone.w}
                  height={zone.h}
                  fill="none"
                  stroke={isBlack ? "rgba(255,255,255,0.25)" : "rgba(0,0,0,0.16)"}
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

            {/* Light and grain over everything on the shirt, print included. */}
            <g clipPath="url(#shirtClip)" pointerEvents="none">
              <rect x="-10" y="60" width="420" height="420" fill="url(#fabricRound)" />
              <rect x="-10" y="60" width="420" height="420" fill="url(#fabricLight)" />
              <rect
                x="-10"
                y="60"
                width="420"
                height="420"
                filter="url(#fabricGrain)"
                opacity={palette.grainOpacity}
                style={{ mixBlendMode: palette.grainBlend }}
              />
            </g>

            <ShirtMeasurements
              widthCm={SIZE_MEASUREMENTS[size].width}
              lengthCm={SIZE_MEASUREMENTS[size].height}
            />

            {isGenerating && (
              <path d={outline} fill={isBlack ? "rgba(255,255,255,0.08)" : "rgba(255,255,255,0.55)"} className="animate-pulse" />
            )}
          </svg>
        </div>

        {secondsLeft !== null && (
          <div
            className="absolute inset-0 flex items-center justify-center pointer-events-none"
            role="timer"
            aria-live="polite"
            aria-label={secondsLeft > 0 ? `About ${secondsLeft} seconds left` : "Almost there"}
          >
            <div className="glass-card flex flex-col items-center gap-1 px-5 py-4">
              <svg width="64" height="64" viewBox="0 0 64 64" aria-hidden="true">
                <circle cx="32" cy="32" r={RING_RADIUS} fill="none" stroke="rgba(0,0,0,0.08)" strokeWidth="5" />
                <circle
                  cx="32"
                  cy="32"
                  r={RING_RADIUS}
                  fill="none"
                  stroke="currentColor"
                  strokeWidth="5"
                  strokeLinecap="round"
                  strokeDasharray={RING_LENGTH}
                  strokeDashoffset={RING_LENGTH * (1 - secondsLeft / GENERATION_COUNTDOWN_SECONDS)}
                  transform="rotate(-90 32 32)"
                  className="text-primary"
                  style={{ transition: "stroke-dashoffset 0.9s linear" }}
                />
                <text x="32" y="38" textAnchor="middle" className="fill-primary font-label-bold" fontSize="18">
                  {secondsLeft > 0 ? secondsLeft : "…"}
                </text>
              </svg>
              <span className="text-xs font-label-bold text-primary">
                {secondsLeft > 0 ? "Generating your design" : "Almost there…"}
              </span>
            </div>
          </div>
        )}
      </div>

      <p className="text-center text-xs text-secondary mt-1">
        {showsPrint
          ? `Print area: ${zone.widthIn} × ${zone.heightIn} in`
          : `Your print is on the ${zone.side}.`}
      </p>

      {/* Zoom controls under the shirt, so they never cover its hem. */}
      <div className="mt-2 flex justify-center">
        <div className="glass-card p-2 flex justify-between items-center gap-2">
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
