# Terrain

TitanForge terrain starts as cheap preview artifacts before full Minecraft export.

## First Heightmap Preview

The first terrain pass reads a `mask-layout` JSON artifact, resolves the source PNG mask, and writes a grayscale heightmap preview.

The layout stores the mask path relative to the layout file. It is resolved as: absolute path as-is; otherwise relative to the layout's folder; otherwise (older layouts) relative to the current working directory. `--mask` overrides all of this.

```powershell
$env:PYTHONPATH = "src"
python -m titanforge mask-layout path\to\mask.png out\layout.json
python -m titanforge heightmap-preview out\layout.json out\heightmap-preview.png
```

To render from a cleaned mask while preserving the original layout:

```powershell
python -m titanforge mask-cleanup-preview path\to\mask.png out\mask-cleanup-preview.png
python -m titanforge heightmap-preview out\layout.json out\heightmap-cleaned-preview.png --mask out\mask-cleanup-preview.png
```

For a generated smoke-test input:

```powershell
python -m titanforge demo-mask out\demo-mask.png --width 128 --height 128
python -m titanforge mask-layout out\demo-mask.png out\demo-layout.json
python -m titanforge heightmap-preview out\demo-layout.json out\demo-heightmap-preview.png
```

## Initial Height Rules

These are diagnostic grayscale values, not final Minecraft Y values.

| Zone | Preview Value |
| --- | --- |
| `water` | `38` |
| `beach` | `92` |
| `port` | `104` |
| `road` | `112` |
| `city` | `122` |
| `forest` | `132` |
| `land` | `140` |
| `mountain` | `220` |
| `void` | transparent |

Unknown colors are rendered as `#ff00ff` so bad masks remain visible.

## Design Rule

Keep this pass simple. It exists to verify map intent before adding smoothing, coastline cleanup, erosion-style filters, water depth, or Minecraft exporters.

For normal use, prefer `build-location`; it runs the mask, layout, heightmap, and report steps together. Add `--use-cleanup-for-heightmap` when tiny water/land noise should be cleaned before terrain preview.
