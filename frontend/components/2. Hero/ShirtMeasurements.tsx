import { MEASUREMENTS } from "@/utils/shirtShape";

interface ShirtMeasurementsProps {
  widthCm: number;
  lengthCm: string;
}

const INK = "#111111";
const CAP = 8;
// In shirt units: the labels scale with the drawing, so they are sized to stay
// readable (about 12 px) on the smallest preview.
const FONT_SIZE = 19;
const PILL = { thickness: 30, widthLabel: 86, lengthLabel: 116 };

/**
 * The size chart's width and length, drawn inside the shirt's SVG (see
 * MEASUREMENTS). Being part of the same drawing, the lines and labels scale
 * with the shirt at its own aspect ratio: never stretched.
 */
export default function ShirtMeasurements({ widthCm, lengthCm }: ShirtMeasurementsProps) {
  const { width, length } = MEASUREMENTS;
  const widthMid = (width.left + width.right) / 2;
  const lengthMid = (length.top + length.bottom) / 2;

  return (
    <g pointerEvents="none" aria-hidden="true">
      {/* Width: dashed guides down from the hem, the dimension line between them. */}
      <g stroke={INK} strokeOpacity="0.35" strokeWidth="1" strokeDasharray="3 3">
        <line x1={width.left} y1={width.hem} x2={width.left} y2={width.lineY + CAP} />
        <line x1={width.right} y1={width.hem} x2={width.right} y2={width.lineY + CAP} />
      </g>
      <g stroke={INK} strokeOpacity="0.8" strokeWidth="1.5">
        <line x1={width.left} y1={width.lineY} x2={width.right} y2={width.lineY} />
        <line x1={width.left} y1={width.lineY - CAP} x2={width.left} y2={width.lineY + CAP} />
        <line x1={width.right} y1={width.lineY - CAP} x2={width.right} y2={width.lineY + CAP} />
      </g>
      <rect
        x={widthMid - PILL.widthLabel / 2}
        y={width.lineY - PILL.thickness / 2}
        width={PILL.widthLabel}
        height={PILL.thickness}
        rx={PILL.thickness / 2}
        fill={INK}
      />
      <text x={widthMid} y={width.lineY} textAnchor="middle" dominantBaseline="central" fontSize={FONT_SIZE} fontWeight="700" fill="#fff">
        {widthCm} cm
      </text>

      {/* Length: from the high point of the shoulder to the hem, right of the sleeve. */}
      <g stroke={INK} strokeOpacity="0.35" strokeWidth="1" strokeDasharray="3 3">
        <line x1={length.neckX} y1={length.top} x2={length.lineX + CAP} y2={length.top} />
        <line x1={length.sideX} y1={length.bottom} x2={length.lineX + CAP} y2={length.bottom} />
      </g>
      <g stroke={INK} strokeOpacity="0.8" strokeWidth="1.5">
        <line x1={length.lineX} y1={length.top} x2={length.lineX} y2={length.bottom} />
        <line x1={length.lineX - CAP} y1={length.top} x2={length.lineX + CAP} y2={length.top} />
        <line x1={length.lineX - CAP} y1={length.bottom} x2={length.lineX + CAP} y2={length.bottom} />
      </g>
      <rect
        x={length.lineX - PILL.thickness / 2}
        y={lengthMid - PILL.lengthLabel / 2}
        width={PILL.thickness}
        height={PILL.lengthLabel}
        rx={PILL.thickness / 2}
        fill={INK}
      />
      <text
        x={length.lineX}
        y={lengthMid}
        textAnchor="middle"
        dominantBaseline="central"
        fontSize={FONT_SIZE}
        fontWeight="700"
        fill="#fff"
        transform={`rotate(90 ${length.lineX} ${lengthMid})`}
      >
        {lengthCm} cm
      </text>
    </g>
  );
}
