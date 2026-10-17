/**
 * The preview shirt's shape, in the print-area coordinate system of
 * utils/printAreas.ts: the torso spans x 80..320 (20 in at 12 units per inch,
 * a size M chest), the shoulders sit at y 94 and the hem at y 466..473. Every
 * print placement lies inside the torso; move both together. The sleeves
 * reach x -4..404, past the torso, like a regular-fit tee's.
 *
 * A set-in-sleeve tee: sloped shoulders, sleeves angled down and out, a body
 * that hangs straight to a slightly curved hem, and a ribbed crew neck.
 */

import type { ShirtSide } from "@/utils/printAreas";

export type GarmentColor = "bg-white" | "bg-black";

// From the right neck point clockwise round the body and back to the left one.
const BODY = [
  "C 268,80 296,85 318,94", //   right shoulder, sloping down
  "C 350,104 384,146 404,202", // right sleeve, top edge
  "L 360,228", //                 right cuff
  "C 348,212 334,192 322,172", // right underarm
  "C 323,260 323,380 320,466", // right side
  "Q 200,480 80,466", //          hem
  "C 77,380 77,260 78,172", //    left side
  "C 66,192 52,212 40,228", //    left underarm
  "L -4,202", //                  left cuff
  "C 16,146 50,104 82,94", //     left sleeve, top edge
  "C 104,85 132,80 158,76", //    left shoulder
  "Z",
].join(" ");

/** The garment's silhouette; the front has the deep crew neckline, the back a shallow one. */
export const SHIRT_OUTLINE: Readonly<Record<ShirtSide, string>> = {
  front: `M 158,76 C 172,112 228,112 242,76 ${BODY}`,
  back: `M 158,76 Q 200,66 242,76 ${BODY}`,
};

/** Seen through the front neckline: the inside of the back panel. */
export const NECK_INSIDE = "M 158,76 Q 200,62 242,76 C 228,112 172,112 158,76 Z";

/** The ribbed collar band and the light catching its edge. */
export const COLLAR: Readonly<Record<ShirtSide, { band: string; sheen: string }>> = {
  front: { band: "M 160,78 C 174,109 226,109 240,78", sheen: "M 163,81 C 176,106 224,106 237,81" },
  back: { band: "M 160,77 Q 200,69 240,77", sheen: "M 163,79 Q 200,72 237,79" },
};

/** The back collar band, visible inside the front neckline. */
export const INNER_BACK_COLLAR = "M 160,77 Q 200,64 240,77";

/** Where the sleeves are sewn to the body. */
export const ARMHOLE_SEAMS = ["M 318,94 C 310,122 312,150 322,172", "M 82,94 C 90,122 88,150 78,172"];

/** Double-needle stitching a few millimetres in from each hem. */
export const HEM_STITCHES = [
  "M 81,456 Q 200,470 319,456",
  "M 81,459.5 Q 200,473.5 319,459.5",
  "M 398.4,195 L 354.4,221",
  "M 1.6,195 L 45.6,221",
];

/** Soft folds where fabric gathers under the arms and sleeves. Drawn blurred. */
export const FOLDS = [
  { d: "M 322,176 Q 300,200 290,240", width: 10 },
  { d: "M 78,176 Q 100,200 110,240", width: 10 },
  { d: "M 360,226 C 348,210 334,192 322,174", width: 13 },
  { d: "M 40,226 C 52,210 66,192 78,174", width: 13 },
];

export interface ShirtPalette {
  fabric: string;
  /** The silhouette's edge, so a white shirt still reads against a light backdrop. */
  edge: string;
  seam: string;
  stitch: string;
  collarBand: string;
  collarSheen: string;
  neckInside: string;
  /** Fold shading: colour and how strongly it shows on this fabric. */
  fold: string;
  foldOpacity: number;
  /** Fabric grain: how strongly it shows, and how it combines with the colour. */
  grainOpacity: number;
  grainBlend: "multiply" | "screen";
}

/** Each garment colour's palette (Strategy by colour): the shape is shared. */
export const SHIRT_PALETTES: Readonly<Record<GarmentColor, ShirtPalette>> = {
  "bg-white": {
    fabric: "#FFFFFF",
    edge: "rgba(0,0,0,0.10)",
    seam: "rgba(0,0,0,0.09)",
    stitch: "rgba(0,0,0,0.14)",
    collarBand: "rgba(0,0,0,0.06)",
    collarSheen: "rgba(255,255,255,0.9)",
    neckInside: "#ECECEC",
    fold: "#000000",
    foldOpacity: 0.07,
    grainOpacity: 0.08,
    grainBlend: "multiply",
  },
  "bg-black": {
    fabric: "#1C1C1E",
    edge: "rgba(255,255,255,0.05)",
    seam: "rgba(255,255,255,0.07)",
    stitch: "rgba(255,255,255,0.11)",
    collarBand: "rgba(255,255,255,0.07)",
    collarSheen: "rgba(255,255,255,0.06)",
    neckInside: "#0E0E0F",
    fold: "#000000",
    foldOpacity: 0.45,
    grainOpacity: 0.07,
    grainBlend: "screen",
  },
};

/**
 * Where the size measurements are drawn, in the same coordinates as the
 * shirt, so they scale with it evenly and point at what they measure: the
 * width across the torso under the hem, the length from the high point of
 * the shoulder down to the hem, to the right of the sleeve.
 */
export const MEASUREMENTS = {
  width: { left: 80, right: 320, hem: 470, lineY: 500 },
  length: { top: 76, bottom: 470, neckX: 246, sideX: 324, lineX: 428 },
} as const;
