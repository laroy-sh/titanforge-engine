# Masks

TitanForge masks are small, inspectable input images used to describe map intent before any Minecraft export exists.

The first mask pass supports exact-color PNG masks. It is intentionally simple: the engine should report what it sees instead of guessing too early.

## Default Zone Palette

| Zone | Color | Meaning |
| --- | --- | --- |
| `water` | `#0066ff` | Ocean, lakes, canals, and major water. |
| `land` | `#3baa35` | General buildable land. |
| `mountain` | `#777777` | High terrain and cliffs. |
| `beach` | `#c2b280` | Sand, coast, and shoreline transition. |
| `road` | `#404040` | Roads, streets, paths, and hard connections. |
| `forest` | `#1f7a1f` | Trees and dense vegetation. |
| `city` | `#b44a4a` | Settlement, district, and building mass. |
| `port` | `#d69a2d` | Docks, harbor, cranes, and waterfront industry. |
| `void` | transparent | Ignored cells. |

## Current CLI

```powershell
$env:PYTHONPATH = "src"
python -m titanforge demo-mask out\demo-mask.png --width 128 --height 128
python -m titanforge mask-info path\to\mask.png
python -m titanforge mask-preview path\to\mask.png out\mask-preview.png
python -m titanforge mask-cleanup-preview path\to\mask.png out\mask-cleanup-preview.png
python -m titanforge mask-layout path\to\mask.png out\layout.json
```

`demo-mask` writes a deterministic toy island mask. It exists for smoke testing the current pipeline without drawing a new input image by hand.

The command prints image size, known zone counts, and unknown colors. Unknown colors are not errors yet; they are early feedback that the mask needs cleanup or a custom palette.

`mask-preview` writes a normalized PNG:

- Known zone colors are preserved.
- Transparent pixels remain transparent.
- Unknown colors are rendered as `#ff00ff` so bad mask data is visible immediately.

`mask-cleanup-preview` writes a conservative cleanup PNG:

- Tiny water specks surrounded by land become land.
- Tiny land specks surrounded by water become water.
- The original mask is not modified.
- This is a preview pass, not final coastline generation.

The cleaned PNG can be used as a heightmap input with `heightmap-preview --mask` or `build-location --use-cleanup-for-heightmap`.

`mask-layout` writes a neutral JSON artifact:

- source mask path (relative to the layout file, forward slashes)
- world width and length
- known and unknown pixel counts
- zone IDs, labels, colors, pixel counts, and percentages
- unknown color list

This is not final terrain. It is the first machine-readable contract between image input and later generation passes.

The first consumer is `heightmap-preview`, documented in `TERRAIN.md`.

For normal use, prefer `build-location`; it creates a complete early location pack from a user mask or deterministic demo input.

## Design Rule

Do not guess fuzzy colors in the first pass. Exact colors make bugs visible and keep the first pipeline deterministic.
