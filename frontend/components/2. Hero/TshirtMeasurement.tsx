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
      preserveAspectRatio="none"
    >
      {/* ---------- WIDTH ---------- */}

      {/* Main horizontal line */}
      <line
        x1="14"
        y1="12"
        x2="276"
        y2="12"
        stroke="#000"
        strokeWidth="1"
      />

      {/* Short end caps */}
      <line
        x1="14"
        y1="5"
        x2="14"
        y2="19"
        stroke="#000"
        strokeWidth="1"
      />
      <line
        x1="276"
        y1="5"
        x2="276"
        y2="19"
        stroke="#000"
        strokeWidth="1"
      />

      {/* Width label */}
      <rect
        x="120"
        y="2"
        width="60"
        height="16"
        rx="9"
        fill="#111"
        opacity="0.95"
      />

      <text
        x="150"
        y="10"
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
        x1="285"
        y1="22"
        x2="285"
        y2="328"
        stroke="#000"
        strokeWidth="1"
      />

      {/* Short top/bottom caps */}
      <line
        x1="290"
        y1="22"
        x2="278"
        y2="22"
        stroke="#000"
        strokeWidth="1"
      />

      <line
        x1="290"
        y1="328"
        x2="278"
        y2="328"
        stroke="#000"
        strokeWidth="1"
      />

      {/* Height label */}
      <rect
        x="277"
        y="140"
        width="16"
        height="60"
        rx="9"
        fill="#111"
        opacity="0.95"
      />

      <text
        x="286"
        y="174"
        textAnchor="middle"
        dominantBaseline="middle"
        fontSize="8"
        fill="#fff"
        fontWeight="700"
        transform="rotate(90 288 170)"
      >
        {SIZE_MEASUREMENTS[size]?.height} cm
      </text>
    </svg>
  );
};

export default TshirtMeasurement;
