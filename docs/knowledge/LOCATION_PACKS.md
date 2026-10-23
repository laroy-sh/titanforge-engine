# Location Packs

Location packs are the first tangible TitanForge output folder. They are not Minecraft worlds yet.

The goal is to collect all early artifacts needed to review a location idea:

```text
location/
  mask.png
  mask-preview.png
  mask-cleanup-preview.png
  layout.json
  heightmap-preview.png
  report.txt
  manifest.json
```

## Build From Demo Input

```powershell
$env:PYTHONPATH = "src"
python -m titanforge build-location out\demo-location --width 128 --height 128
```

No `--input` means demo mode. This is useful for smoke testing.

## Build From User Mask

```powershell
$env:PYTHONPATH = "src"
python -m titanforge build-location out\my-location --input path\to\mask.png
```

The input mask is copied into the pack as `mask.png`.

`layout.json` refers to the mask relative to its own folder (`"path": "mask.png"`), so a pack keeps working after it is moved or opened from another working directory.

## Cleanup As Terrain Input

By default, `heightmap-preview.png` is rendered from the original `mask.png`.

Use this when you want tiny water/land specks cleaned before terrain preview:

```powershell
python -m titanforge build-location out\my-location --input path\to\mask.png --use-cleanup-for-heightmap
```

The original mask and report still remain in the pack. The manifest records which mask was used for heightmap generation:

```json
{
  "terrain": {
    "cleanupApplied": true,
    "heightmapSource": "mask-cleanup-preview.png"
  }
}
```

## Validation

The pack writes `report.txt` and `manifest.json`.

Warnings do not stop the build. Errors return a non-zero CLI exit code.

Current warnings include:

- unknown mask colors
- missing water
- missing land
- mostly water
- mostly land

`mask-cleanup-preview.png` is included to reveal tiny water/land noise before terrain generation. It can optionally be used for `heightmap-preview.png`, but it does not replace `mask.png`.

## Product Meaning

This is the first useful "touch it" version of TitanForge:

```text
PNG mask or generated demo
-> visible mask preview
-> neutral layout JSON
-> heightmap preview
-> validation report
```

Minecraft export comes later. Location packs keep early work inspectable before expensive terrain and exporter passes exist.
