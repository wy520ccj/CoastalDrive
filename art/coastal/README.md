# CoastalDrive coastal environment kit

This directory contains the editable Blender source for a small, bright coastal environment set. The assets use warm limestone, terracotta, cream, navy, sea glass, deep green and sage materials with rough, nonmetallic surfaces. Nature silhouettes use asymmetrical low-poly clusters and layered forms for readable roadside scale.

## Source and regeneration

- Editable grouped scene: `art/coastal/coastal_kit.blend`
- Deterministic build/export script: `tools/blender/build_coastal_kit.py`
- Exports: `assets/game/environment/models/*.glb`
- Dimensions, triangle counts and provenance: `assets/game/environment/kit-manifest.json`
- Blender version used: 5.2.2

From the project root, regenerate with:

```powershell
& 'B:\steam\steamapps\common\Blender\blender.exe' --background --python tools/blender/build_coastal_kit.py
```

Each asset is a separate named collection with a joined, editable mesh and shared palette materials. In the Blender source, each asset's ground contact is at local Z=0 and its footprint is centered at the origin. Export applies Blender's glTF coordinate conversion. The temporary asset-board positions in the source scene are removed for each individual GLB export.

## Included assets and provenance

All 12 exported models are original CoastalDrive geometry. They contain no bundled textures, runtime dependencies, or third-party meshes. The supplied Kenney Nature Kit files are retained in `assets/game/nature/` under their existing CC0 license but are not embedded in this kit.

| GLB | Contents | Source / license |
|---|---|---|
| `pine_tall_a.glb`, `pine_tall_b.glb` | Two broad, irregular layered pines with exposed branches | Project-generated; no external source assets |
| `bush_round_a.glb`, `bush_round_b.glb` | Two asymmetric shrub clusters | Project-generated; no external source assets |
| `rock_coastal_a.glb`, `rock_coastal_b.glb` | Faceted limestone boulders with broken pale seams | Project-generated; no external source assets |
| `flowers_coastal_a.glb` | Four-stem coastal flowers | Project-generated; no external source assets |
| `cliff_coastal_a.glb` | Continuous tapered limestone mass with subtle strata and a flat grassy cap | Project-generated; no external source assets |
| `lighthouse_coastal_a.glb` | Tapered masonry tower, lantern, glazing and gallery | Project-generated; no external source assets |
| `coastal_house_a.glb` | Limewashed cottage, terracotta roof, shutters, porch and chimney | Project-generated; no external source assets |
| `road_chevron_sign_a.glb` | Reflective chevron road sign | Project-generated; no external source assets |
| `coastal_lamp_a.glb` | Coastal lamp with glass lantern | Project-generated; no external source assets |

The manifest lists measured bounds and triangle counts for every export. The complete set is kept below a 50,000-triangle budget. The kit props are visual-only and create no collision bodies. Simulation remains the existing authority for collision and physical behavior; this kit does not change it.
