"use client";

import { TShirtPreviewProps } from "@/app/interfaces/banner";

const COLOR_MAP: Record<string, {
  base: string;
  seam: string;
  collarBand: string;
  collarSheen: string; }> = {
  "bg-white": {
    base:        "#F4F4F4",
    seam:        "rgba(0,0,0,0.07)",
    collarBand:  "rgba(0,0,0,0.09)",
    collarSheen: "rgba(255,255,255,0.80)",
  },
  "bg-gray": {
    base:        "#C8C8C8",
    seam:        "rgba(0,0,0,0.10)",
    collarBand:  "rgba(0,0,0,0.13)",
    collarSheen: "rgba(255,255,255,0.45)",
  },
  "bg-black": {
    base:        "#1A1A1A",
    seam:        "rgba(255,255,255,0.06)",
    collarBand:  "rgba(255,255,255,0.08)",
    collarSheen: "rgba(255,255,255,0.06)",
  },
};

const PLACEMENT_ZONES: Record<string, { x: number; y: number; w: number; h: number; back?: boolean }> = {
  "Center Chest":     { x: 128, y: 182, w: 144, h: 120 },
  "Left Top Chest":   { x:  96, y: 182, w:  78, h:  78 },
  "Right Top Chest":  { x: 226, y: 182, w:  78, h:  78 },
  "Left Bottom":      { x:  90, y: 308, w: 110, h: 132 },
  "Right Bottom":     { x: 200, y: 308, w: 110, h: 132 },
  "Center Bottom":    { x: 118, y: 300, w: 164, h: 148 },
  "Oversized Center": { x:  88, y: 168, w: 224, h: 256 },
  "Full Back":        { x:  88, y: 174, w: 224, h: 252, back: true },
  "Back Upper":       { x:  88, y: 174, w: 224, h: 124, back: true },
  "Back Lower":       { x:  88, y: 308, w: 224, h: 140, back: true },
};

const BODY_PATH = [
  "L 324,70",
  "C 366,52 400,112 394,188",
  "L 356,202",
  "Q 338,194 320,170",
  "L 320,460",
  "Q 315,472 300,472",
  "L 100,472",
  "Q 85,472 80,460",
  "L 80,170",
  "Q 62,194 44,202",
  "L 6,188",
  "C 0,112 34,52 76,70",
  "Z",
].join(" ");

const SHIRT_PATH_FRONT = `M 160,80 C 175,112 225,112 240,80 ${BODY_PATH}`;
const SHIRT_PATH_BACK  = `M 160,80 Q 200,68 240,80 ${BODY_PATH}`;

export default function TShirtPreview({
  color,
  placement,
  designUrl,
  isGenerating = false,
}: TShirtPreviewProps) {
  const c       = COLOR_MAP[color] ?? COLOR_MAP["bg-white"];
  const zone    = PLACEMENT_ZONES[placement] ?? PLACEMENT_ZONES["Center Chest (Standard)"];
  const isBack  = zone.back === true;
  const isBlack = color === "bg-black";

  const shirtPath   = isBack ? SHIRT_PATH_BACK : SHIRT_PATH_FRONT;
  const collarFront = "M 160,80 C 175,112 225,112 240,80";
  const collarBack  = "M 160,80 Q 200,68 240,80";
  const collarPath  = isBack ? collarBack : collarFront;
  const sheenFront  = "M 163,83 C 178,110 222,110 237,83";
  const sheenBack   = "M 163,80 Q 200,71 237,80";
  const sheenPath   = isBack ? sheenBack : sheenFront;

  return (
    <svg
      viewBox="-67 -80 534 640"
      xmlns="http://www.w3.org/2000/svg"
      className="w-full h-full"
      aria-label={isBack ? "T-shirt back preview" : "T-shirt front preview"}
    >
      <defs>
        <filter id="shirtShadow" x="-8%" y="-4%" width="116%" height="116%">
          <feDropShadow dx="0" dy="10" stdDeviation="14" floodColor="rgba(0,0,0,0.22)" />
        </filter>
        <clipPath id="shirtClip">
          <path d={shirtPath} />
        </clipPath>
      </defs>

      <path
        d={shirtPath}
        fill={c.base}
        filter="url(#shirtShadow)"
        style={{ transition: "fill 0.45s ease" }}
      />

      <path
        d={collarPath}
        fill="none"
        stroke={c.collarBand}
        strokeWidth="9"
        strokeLinecap="round"
      />
      <path
        d={sheenPath}
        fill="none"
        stroke={c.collarSheen}
        strokeWidth="2.5"
        strokeLinecap="round"
        opacity="0.8"
      />

      {isBack && (
        <rect
          x="193"
          y="76"
          width="14" height="20"
          fill={isBlack ? "rgba(255,255,255,0.10)" : "rgba(0,0,0,0.07)"}
          stroke={isBlack ? "rgba(255,255,255,0.05)" : "rgba(0,0,0,0.04)"}
          strokeWidth="1"
          rx="1.5"
        />
      )}

      <line x1="160" y1="80" x2="76"  y2="70" stroke={c.seam} strokeWidth="1.5" />
      <line x1="240" y1="80" x2="324" y2="70" stroke={c.seam} strokeWidth="1.5" />

      <path d="M 44,202 L 6,188"    fill="none" stroke={c.seam} strokeWidth="2" />
      <path d="M 356,202 L 394,188" fill="none" stroke={c.seam} strokeWidth="2" />

      {designUrl && (
        <g
          clipPath="url(#shirtClip)"
          style={{
            opacity: isGenerating ? 0.15 : 1,
            transition: "opacity 0.55s ease",
          }}
        >
          <image
            href={designUrl}
            x={zone.x}
            y={zone.y}
            width={zone.w}
            height={zone.h}
            preserveAspectRatio="xMidYMid meet"
            style={{
              mixBlendMode: isBlack ? "screen" : "multiply",
              transition: "x 0.5s ease, y 0.5s ease, width 0.5s ease, height 0.5s ease",
            }}
          />
        </g>
      )}

      {isGenerating && (
        <path
          d={shirtPath}
          fill={isBlack ? "rgba(255,255,255,0.08)" : "rgba(255,255,255,0.55)"}
          className="animate-pulse"
        />
      )}
    </svg>
  );
}
