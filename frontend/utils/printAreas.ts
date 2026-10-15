/**
 * Where each print placement sits on the preview shirt, at its real size.
 *
 * The inch sizes mirror order-service's OrderPricingService.PRINT_AREAS_INCHES:
 * the server measures the order's print size and DPI from that table, so the
 * preview draws the same rectangle. Change both together.
 *
 * The preview shirt's torso is 240 SVG units across (x 80..320), the flat
 * chest width of a size M (about 20 in), so one inch is PX_PER_INCH units.
 * Drawing every placement at that one scale is what makes a chest logo look
 * as small next to the shirt as it will be printed.
 */

export type Placement =
  | "Center Chest"
  | "Left Top Chest"
  | "Right Top Chest"
  | "Left Bottom"
  | "Right Bottom"
  | "Center Bottom"
  | "Oversized Center"
  | "Full Back"
  | "Back Upper"
  | "Back Lower";

export type ShirtSide = "front" | "back";

export const PX_PER_INCH = 12;

interface PrintArea {
  widthIn: number;
  heightIn: number;
  /** Horizontal centre and top edge on the preview shirt, in SVG units. */
  centerX: number;
  top: number;
  side: ShirtSide;
}

const PRINT_AREAS: Readonly<Record<Placement, PrintArea>> = {
  "Center Chest": { widthIn: 12, heightIn: 10, centerX: 200, top: 150, side: "front" },
  "Left Top Chest": { widthIn: 5, heightIn: 5, centerX: 140, top: 150, side: "front" },
  "Right Top Chest": { widthIn: 5, heightIn: 5, centerX: 260, top: 150, side: "front" },
  "Left Bottom": { widthIn: 8, heightIn: 10, centerX: 145, top: 320, side: "front" },
  "Right Bottom": { widthIn: 8, heightIn: 10, centerX: 255, top: 320, side: "front" },
  "Center Bottom": { widthIn: 11, heightIn: 10, centerX: 200, top: 310, side: "front" },
  "Oversized Center": { widthIn: 15, heightIn: 18, centerX: 200, top: 140, side: "front" },
  "Full Back": { widthIn: 15, heightIn: 18, centerX: 200, top: 130, side: "back" },
  "Back Upper": { widthIn: 15, heightIn: 8, centerX: 200, top: 130, side: "back" },
  "Back Lower": { widthIn: 15, heightIn: 9.5, centerX: 200, top: 320, side: "back" },
};

export const PLACEMENTS = Object.keys(PRINT_AREAS) as Placement[];

export const isPlacement = (value: string): value is Placement => value in PRINT_AREAS;

export interface PlacementZone {
  x: number;
  y: number;
  w: number;
  h: number;
  side: ShirtSide;
  widthIn: number;
  heightIn: number;
}

/** The placement's rectangle on the preview shirt; an unknown name falls back to Center Chest. */
export const placementZone = (placement: string): PlacementZone => {
  const area = PRINT_AREAS[isPlacement(placement) ? placement : "Center Chest"];
  const w = area.widthIn * PX_PER_INCH;
  const h = area.heightIn * PX_PER_INCH;
  return { x: area.centerX - w / 2, y: area.top, w, h, side: area.side, widthIn: area.widthIn, heightIn: area.heightIn };
};
