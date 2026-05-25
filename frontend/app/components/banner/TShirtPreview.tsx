"use client";

interface TShirtPreviewProps {
  color: "bg-white" | "bg-gray" | "bg-black";
  placement: string;
  designUrl: string;
  isGenerating?: boolean;
}

const COLOR_MAP: Record<string, {
  base: string;
  shade: string;
  highlight: string;
  seam: string;
  collarBand: string;
  collarSheen: string; }> = {
  "bg-white": {
    base:        "#F4F4F4",
    shade:       "rgba(0,0,0,0.06)",
    highlight:   "rgba(255,255,255,0.95)",
    seam:        "rgba(0,0,0,0.07)",
    collarBand:  "rgba(0,0,0,0.09)",
    collarSheen: "rgba(255,255,255,0.80)",
  },
  "bg-gray": {
    base:        "#C8C8C8",
    shade:       "rgba(0,0,0,0.11)",
    highlight:   "rgba(255,255,255,0.50)",
    seam:        "rgba(0,0,0,0.10)",
    collarBand:  "rgba(0,0,0,0.13)",
    collarSheen: "rgba(255,255,255,0.45)",
  },
  "bg-black": {
    base:        "#1A1A1A",
    shade:       "rgba(0,0,0,0.55)",
    highlight:   "rgba(255,255,255,0.07)",
    seam:        "rgba(255,255,255,0.06)",
    collarBand:  "rgba(255,255,255,0.08)",
    collarSheen: "rgba(255,255,255,0.06)",
  },
};

// All zones sit within the shirt body (x: 80–320, y: 168–460)
const PLACEMENT_ZONES: Record<string, { x: number; y: number; w: number; h: number; back?: boolean }> = {
  // ── Front zones ──────────────────────────────────────────────────
  "Center Chest":     { x: 128, y: 182, w: 144, h: 120 },  // centred upper chest
  "Left Top Chest":   { x:  96, y: 182, w:  78, h:  78 },  // small logo, upper-left
  "Right Top Chest":  { x: 226, y: 182, w:  78, h:  78 },  // small logo, upper-right
  "Left Bottom":      { x:  90, y: 308, w: 110, h: 132 },  // lower-left print
  "Right Bottom":     { x: 200, y: 308, w: 110, h: 132 },  // lower-right print
  "Center Bottom":    { x: 118, y: 300, w: 164, h: 148 },  // centred lower print
  "Oversized Center": { x:  88, y: 168, w: 224, h: 256 },  // large full-body print
  // ── Back zones ───────────────────────────────────────────────────
  "Full Back":        { x:  88, y: 174, w: 224, h: 252, back: true }, // full back body
  "Back Upper":       { x:  88, y: 174, w: 224, h: 124, back: true }, // upper back only
  "Back Lower":       { x:  88, y: 308, w: 224, h: 140, back: true }, // lower back only
};

// Shared body/sleeve path (everything after the collar curve)
const BODY_PATH = [
  "L 324,70",
  "L 387,106",
  "Q 396,148 394,188",
  "L 356,202",
  "Q 338,194 320,170",
  "L 320,460",
  "Q 315,472 300,472",
  "L 100,472",
  "Q 85,472 80,460",
  "L 80,170",
  "Q 62,194 44,202",
  "L 6,188",
  "Q 4,148 13,106",
  "L 76,70",
  "Z",
].join(" ");

// Front: deep U-curve crew neck (collar opening visible)
const SHIRT_PATH_FRONT = `M 160,80 C 175,112 225,112 240,80 ${BODY_PATH}`;

// Back: very shallow upward bow — back neckline sits higher, almost straight
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
  // collar band traces the same curve as the neckline opening
  const collarFront = "M 160,80 C 175,112 225,112 240,80";
  const collarBack  = "M 160,80 Q 200,68 240,80";
  const collarPath  = isBack ? collarBack : collarFront;
  // sheen sits ~3px inside the collar band
  const sheenFront  = "M 163,83 C 178,110 222,110 237,83";
  const sheenBack   = "M 163,80 Q 200,71 237,80";
  const sheenPath   = isBack ? sheenBack : sheenFront;

  return (
    // viewBox is 1.33× the shirt coordinate space → shirt appears at 0.75× visual size,
    // perfectly centred. Same 5:6 aspect ratio as the original 0 0 400 480.
    <svg
      viewBox="-67 -80 534 640"
      xmlns="http://www.w3.org/2000/svg"
      className="w-full h-full"
      aria-label={isBack ? "T-shirt back preview" : "T-shirt front preview"}
    >
      <defs>
        {/* Fabric lighting gradient — light from top-left */}
        <linearGradient id="fabricLight" x1="0.1" y1="0" x2="0.9" y2="1">
          <stop offset="0%"   stopColor={c.highlight} stopOpacity="1" />
          <stop offset="45%"  stopColor="transparent" stopOpacity="0" />
          <stop offset="100%" stopColor={c.shade}     stopOpacity="1" />
        </linearGradient>

        {/* Side-edge shadow gradient */}
        <linearGradient id="sideShade" x1="0" y1="0" x2="1" y2="0">
          <stop offset="0%"   stopColor={c.shade} stopOpacity="0.7" />
          <stop offset="15%"  stopColor="transparent" stopOpacity="0" />
          <stop offset="85%"  stopColor="transparent" stopOpacity="0" />
          <stop offset="100%" stopColor={c.shade} stopOpacity="0.5" />
        </linearGradient>

        {/* Drop shadow on the whole shirt */}
        <filter id="shirtShadow" x="-8%" y="-4%" width="116%" height="116%">
          <feDropShadow dx="0" dy="10" stdDeviation="14" floodColor="rgba(0,0,0,0.22)" />
        </filter>

        {/* Clip to current shirt silhouette */}
        <clipPath id="shirtClip">
          <path d={shirtPath} />
        </clipPath>
      </defs>

      {/* ── Base shirt fill ── */}
      <path
        d={shirtPath}
        fill={c.base}
        filter="url(#shirtShadow)"
        style={{ transition: "fill 0.45s ease" }}
      />

      {/* ── Fabric lighting overlay ── */}
      <path d={shirtPath} fill="url(#fabricLight)" opacity="0.55" />
      <path d={shirtPath} fill="url(#sideShade)"   opacity="0.5"  />

      {/* ── Collar rib band ── */}
      <path
        d={collarPath}
        fill="none"
        stroke={c.collarBand}
        strokeWidth="9"
        strokeLinecap="round"
      />
      {/* Collar inner sheen highlight */}
      <path
        d={sheenPath}
        fill="none"
        stroke={c.collarSheen}
        strokeWidth="2.5"
        strokeLinecap="round"
        opacity="0.8"
      />

      {/* Back view: care-label tag at centre neckline */}
      {isBack && (
        <rect
          x="193" y="76"
          width="14" height="20"
          fill={isBlack ? "rgba(255,255,255,0.10)" : "rgba(0,0,0,0.07)"}
          stroke={isBlack ? "rgba(255,255,255,0.05)" : "rgba(0,0,0,0.04)"}
          strokeWidth="1"
          rx="1.5"
        />
      )}

      {/* ── Shoulder seam lines ── */}
      <line x1="160" y1="80" x2="76"  y2="70" stroke={c.seam} strokeWidth="1.5" />
      <line x1="240" y1="80" x2="324" y2="70" stroke={c.seam} strokeWidth="1.5" />

      {/* ── Sleeve hem / cuff seam lines ── */}
      <path d="M 44,202 L 6,188"    fill="none" stroke={c.seam} strokeWidth="2" />
      <path d="M 356,202 L 394,188" fill="none" stroke={c.seam} strokeWidth="2" />

      {/* ── Centre-fold crease ── */}
      <line
        x1="200" y1={isBack ? 76 : 112} x2="200" y2="470"
        stroke={isBlack ? "rgba(255,255,255,0.025)" : "rgba(0,0,0,0.025)"}
        strokeWidth="1"
        strokeDasharray="5 7"
      />

      {/* ── Design image overlay ── */}
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

      {/* ── Generating pulse overlay ── */}
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
