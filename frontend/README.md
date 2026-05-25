🏆 Recommendation: `@react-three/fiber` + `@react-three/drei`

The only approach that matches AIGEN's luxury brand level. Used by all real production POD platforms (Printful, Printify, etc.)

| | **R3F + drei (3D)** | react-konva | Pure SVG |
|-----------------------|-------------|----------|---|
| Downloads/wk | **3.28M** | 1.49M | — |
| Stars | **30.9k + 9.7k** | 6.3k | — |
| Color quality | ⭐⭐⭐⭐⭐ PBR material | ⭐⭐⭐ multiply blend | ⭐⭐⭐⭐⭐ SVG fill |
| Design placement | ⭐⭐⭐⭐⭐ UV-mapped | ⭐⭐⭐⭐ pixel coords | ⭐⭐⭐ CSS % |
| Visual quality | ⭐⭐⭐⭐⭐ 3D+lighting | ⭐⭐⭐ flat 2D | ⭐⭐ silhouette |
| Bundle (gzip) | ~280KB (lazy) | ~95KB | **0KB** |
| SSR friction | `ssr: false` (solved) | ✅ none | ✅ none |
| 360° spin | ✅ OrbitControls | ❌ | ❌ |

**No dedicated t-shirt/garment React libs exist** — all npm packages with those names return 404.

---

## Suggested architecture

```
HomeBanner (Server Component)
├── TShirtFallback     ← pure SVG, SSR-safe, instant render
└── TShirtViewer3D     ← dynamic(ssr:false), lazy loads
    ├── Canvas (R3F)
    ├── useGLTF('/models/tshirt.glb')
    ├── MeshStandardMaterial color={selectedColor}  ← reactive recolor
    ├── TextureLoader(aiGeneratedImageUrl)           ← design overlay
    ├── PRINT_ZONES map → texture.offset/repeat      ← placement
    └── OrbitControls                                ← spin the shirt

🟢 Option C: Pure SVG T-Shirt + CSS Overlay

**How it works:** An inline `<svg>` containing the shirt outline as a `<path>` element. CSS `fill` prop changes color. An absolutely positioned `<img>` tag (or `<div>` with background-image) overlays the design within a CSS grid/relative container. Placement zones = CSS `top`/`left`/`width`/`height` values as Tailwind classes or CSS vars.

```tsx
// Pure SVG + Tailwind approach — zero dependencies
const PLACEMENT_ZONES = {
  centerChest:    { top: '28%', left: '29%', width: '42%', height: '38%' },
  fullBack:       { top: '22%', left: '20%', width: '60%', height: '55%' },
  smallLeftChest: { top: '25%', left: '28%', width: '22%', height: '22%' },
  oversizedCenter:{ top: '20%', left: '18%', width: '65%', height: '60%' },
} as const;

export function TShirtPreview({ color, placement, designUrl }) {
  const zone = PLACEMENT_ZONES[placement];
  return (
    <div className="relative w-full aspect-square">
      {/* SVG shirt silhouette */}
      <svg viewBox="0 0 400 400" xmlns="http://www.w3.org/2000/svg" 
           className="w-full h-full drop-shadow-lg">
        {/* T-shirt path — collar, sleeves, body */}
        <path d="M100,40 L60,80 L20,120 L60,140 L60,360 L340,360 
                 L340,140 L380,120 L340,80 L300,40 
                 C280,20 260,10 250,30 C240,50 160,50 150,30 
                 C140,10 120,20 100,40 Z"
          fill={color}
          className="transition-colors duration-300"
        />
      </svg>
      {/* Design overlay positioned within shirt body */}
      {designUrl && (
        <div className="absolute pointer-events-none"
             style={{ top: zone.top, left: zone.left, 
                      width: zone.width, height: zone.height }}>
          <img src={designUrl} alt="Design" 
               className="w-full h-full object-contain mix-blend-multiply" />
        </div>
      )}
    </div>
  );
}