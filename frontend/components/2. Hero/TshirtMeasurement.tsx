import { SIZE_MEASUREMENTS } from "@/utils/constants";

type TshirtMeasurementProps = {
  size: keyof typeof SIZE_MEASUREMENTS;
};

const TshirtMeasurement = ({ size }: TshirtMeasurementProps) => {
  return (
    <svg
      className="absolute inset-0 pointer-events-none z-20"
      width="100%"
      height="100%"
      viewBox="0 0 300 340"
      preserveAspectRatio="xMidYMid meet"
    >
      {/* ---------- WIDTH ---------- */}

      {/* Main horizontal line */}
      <line
        x1="70"
        y1="55"
        x2="230"
        y2="55"
        stroke="#000"
        strokeWidth="1"
      />

      {/* Short end caps */}
      <line
        x1="70"
        y1="48"
        x2="70"
        y2="62"
        stroke="#000"
        strokeWidth="1"
      />
      <line
        x1="230"
        y1="48"
        x2="230"
        y2="62"
        stroke="#000"
        strokeWidth="1"
      />

      {/* Width label */}
      <rect
        x="120"
        y="45"
        width="60"
        height="18"
        rx="9"
        fill="#111"
        opacity="0.95"
      />

      <text
        x="150"
        y="55"
        textAnchor="middle"
        dominantBaseline="central"
        alignmentBaseline="middle"
        fontSize="8"
        fill="#fff"
        fontWeight="700"
      >
        {SIZE_MEASUREMENTS[size]?.width} cm
      </text>

      {/* ---------- HEIGHT ---------- */}

      {/* Main vertical line */}
      <line
        x1="265"
        y1="85"
        x2="265"
        y2="275"
        stroke="#000"
        strokeWidth="1"
      />

      {/* Short top/bottom caps */}
      <line
        x1="258"
        y1="85"
        x2="272"
        y2="85"
        stroke="#000"
        strokeWidth="1"
      />

      <line
        x1="258"
        y1="275"
        x2="272"
        y2="275"
        stroke="#000"
        strokeWidth="1"
      />

      {/* Height label */}
      <rect
        x="256"
        y="150"
        width="18"
        height="60"
        rx="9"
        fill="#111"
        opacity="0.95"
      />

      <text
        x="260"
        y="185"
        textAnchor="middle"
        dominantBaseline="middle"
        fontSize="8"
        fill="#fff"
        fontWeight="700"
        transform="rotate(90 265 185)"
      >
        {SIZE_MEASUREMENTS[size]?.height} cm
      </text>
    </svg>
  );
};

export default TshirtMeasurement;