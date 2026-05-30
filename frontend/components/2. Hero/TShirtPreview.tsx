"use client";

import { TShirtPreviewProps } from "@/types/banner";
import {
  COLOR_MAP,
  PLACEMENT_ZONES,
  SHIRT_PATH_BACK,
  SHIRT_PATH_FRONT,
} from "@/utils/constants";

export default function TShirtPreview({
  color,
  placement,
  designUrl,
  isGenerating = false,
}: TShirtPreviewProps) {
  const c       = COLOR_MAP[color] ?? COLOR_MAP["bg-white"];
  const zone    = PLACEMENT_ZONES[placement] ?? PLACEMENT_ZONES["Center Chest"];
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
