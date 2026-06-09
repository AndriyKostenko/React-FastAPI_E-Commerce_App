"use client";

import { useState } from "react";
import { TShirtPreviewProps } from "@/types/banner";
import {
    COLOR_MAP,
    PLACEMENT_ZONES,
    SHIRT_PATH_BACK,
    SHIRT_PATH_FRONT,
} from "@/utils/constants";
import { resolveImageUrl } from "@/utils/resolveImageUrl";

export default function TShirtPreview({
    color,
    placement,
    designUrl,
    isGenerating = false,
}: TShirtPreviewProps) {
    const [zoom, setZoom] = useState(1);
    const MIN_ZOOM = 0.5;
    const MAX_ZOOM = 3;
    const ZOOM_STEP = 0.1;

    const handleZoomIn = () => {
        setZoom((prev) => Math.min(prev + ZOOM_STEP, MAX_ZOOM));
    };

    const handleZoomOut = () => {
        setZoom((prev) => Math.max(prev - ZOOM_STEP, MIN_ZOOM));
    };

    const handleResetZoom = () => {
        setZoom(1);
    };

    const c = COLOR_MAP[color] ?? COLOR_MAP["bg-white"];
    const zone = PLACEMENT_ZONES[placement] ?? PLACEMENT_ZONES["Center Chest"];
    const isBack = zone.back === true;
    const isBlack = color === "bg-black";
    const previewImageUrl = designUrl ? resolveImageUrl(designUrl) : "";

    const shirtPath = isBack ? SHIRT_PATH_BACK : SHIRT_PATH_FRONT;
    const collarFront = "M 160,80 C 175,112 225,112 240,80";
    const collarBack = "M 160,80 Q 200,68 240,80";
    const collarPath = isBack ? collarBack : collarFront;
    const sheenFront = "M 163,83 C 178,110 222,110 237,83";
    const sheenBack = "M 163,80 Q 200,71 237,80";
    const sheenPath = isBack ? sheenBack : sheenFront;

    return (
        <div className="relative w-full h-full flex flex-col">
            {/* T-shirt SVG Container */}
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
                        aria-label={
                            isBack
                                ? "T-shirt back preview"
                                : "T-shirt front preview"
                        }
                    >
            <defs>
                <filter
                    id="shirtShadow"
                    x="-8%"
                    y="-4%"
                    width="116%"
                    height="116%"
                >
                    <feDropShadow
                        dx="0"
                        dy="10"
                        stdDeviation="14"
                        floodColor="rgba(0,0,0,0.22)"
                    />
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
                    width="14"
                    height="20"
                    fill={
                        isBlack ? "rgba(255,255,255,0.10)" : "rgba(0,0,0,0.07)"
                    }
                    stroke={
                        isBlack ? "rgba(255,255,255,0.05)" : "rgba(0,0,0,0.04)"
                    }
                    strokeWidth="1"
                    rx="1.5"
                />
            )}

            <line
                x1="160"
                y1="80"
                x2="76"
                y2="70"
                stroke={c.seam}
                strokeWidth="1.5"
            />
            <line
                x1="240"
                y1="80"
                x2="324"
                y2="70"
                stroke={c.seam}
                strokeWidth="1.5"
            />

            <path
                d="M 44,202 L 6,188"
                fill="none"
                stroke={c.seam}
                strokeWidth="2"
            />
            <path
                d="M 356,202 L 394,188"
                fill="none"
                stroke={c.seam}
                strokeWidth="2"
            />

            {previewImageUrl && (
                <g
                    clipPath="url(#shirtClip)"
                    style={{
                        opacity: isGenerating ? 0.15 : 1,
                        transition: "opacity 0.55s ease",
                    }}
                >
                    <image
                        href={previewImageUrl}
                        x={zone.x}
                        y={zone.y}
                        width={zone.w}
                        height={zone.h}
                        preserveAspectRatio="xMidYMid meet"
                        style={{
                            mixBlendMode: isBlack ? "screen" : "multiply",
                            transition:
                                "x 0.5s ease, y 0.5s ease, width 0.5s ease, height 0.5s ease",
                        }}
                    />
                </g>
            )}

            {isGenerating && (
                <path
                    d={shirtPath}
                    fill={
                        isBlack
                            ? "rgba(255,255,255,0.08)"
                            : "rgba(255,255,255,0.55)"
                    }
                    className="animate-pulse"
                />
            )}
        </svg>
                </div>
            </div>

            {/* Zoom Controls */}
            <div className="fixed bottom-6 left-0 right-0 z-50 flex justify-center">
                <div className="glass-card p-2 flex justify-between items-center gap-2 transition-all duration-300">
                    <div className="flex gap-1">
                        <button
                            onClick={handleZoomOut}
                            disabled={zoom <= MIN_ZOOM}
                            className="h-8 px-2 rounded-lg font-label-bold text-xs bg-white/60 text-primary border border-white/20 hover:bg-white/80 transition-all hover:scale-110 disabled:opacity-50 disabled:cursor-not-allowed"
                            title="Zoom Out"
                        >
                            −
                        </button>
                        <span className="px-2 py-1.5 text-xs font-label-bold text-primary min-w-[40px] text-center">
                            {Math.round(zoom * 100)}%
                        </span>
                        <button
                            onClick={handleZoomIn}
                            disabled={zoom >= MAX_ZOOM}
                            className="h-8 px-2 rounded-lg font-label-bold text-xs bg-white/60 text-primary border border-white/20 hover:bg-white/80 transition-all hover:scale-110 disabled:opacity-50 disabled:cursor-not-allowed"
                            title="Zoom In"
                        >
                            +
                        </button>
                    </div>
                    <button
                        onClick={handleResetZoom}
                        className="bg-brand-lime text-primary px-3 py-1 rounded-full font-label-bold text-xs hover:shadow-md transition-all active:scale-95"
                        title="Reset Zoom"
                    >
                        Reset
                    </button>
                </div>
            </div>
        </div>
    );
}
