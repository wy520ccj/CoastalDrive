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
| `pine_tall_a.glb`, `pine_tall_b.glb` | Six spreading levels of overlapping needle sprays with an exposed lower trunk and spreading boughs | Project-generated; no external source assets |
| `bush_round_a.glb`, `bush_round_b.glb` | Two asymmetric shrub clusters | Project-generated; no external source assets |
| `rock_coastal_a.glb`, `rock_coastal_b.glb` | Connected angular limestone masses with darker lower faces and moss-tinted upper facets | Project-generated; no external source assets |
| `flowers_coastal_a.glb` | Four-stem coastal flowers | Project-generated; no external source assets |
| `cliff_coastal_a.glb` | Continuous tapered limestone mass with subtle strata and a flat grassy cap | Project-generated; no external source assets |
| `lighthouse_coastal_a.glb` | 14 m tapered masonry tower with surface door and windows, lantern glazing and open ring gallery rails | Project-generated; no external source assets |
| `coastal_house_a.glb` | Limewashed cottage, terracotta roof, shutters, porch and chimney | Project-generated; no external source assets |
| `road_chevron_sign_a.glb` | Reflective chevron road sign | Project-generated; no external source assets |
| `coastal_lamp_a.glb` | Coastal lamp with glass lantern | Project-generated; no external source assets |

The manifest lists measured bounds and triangle counts for every export. The complete set stays below a 30,000-triangle budget. The kit props are visual-only and create no collision bodies. Simulation remains the existing authority for collision and physical behavior; this kit does not change it.

## ENV-02 terrain source

`coastal_terrain.blend` contains separate inland, coast, lighthouse-reef and ground-cover objects. The GLB uses vertex colors and world-scaled UVs; production terrain has 24,790 triangles (including 1,800 two-sided grass blades). Kit models total 11,278 triangles; this is the library total, not the scene total.

Regenerate from the repository root, in order:

```powershell
..\CoastalDrive\.venv\Scripts\python.exe tools/environment/export_terrain_data.py --output logs/ENV-02/terrain-input.json
& 'B:\steam\steamapps\common\Blender\blender.exe' -b --python tools/blender/build_coastal_terrain.py -- logs/ENV-02/terrain-input.json
..\CoastalDrive\.venv\Scripts\python.exe tools/environment/make_ground_detail.py
# Use an offline Python with NumPy and Pillow; these are NOT game runtime dependencies.
python tools/environment/bake_shore_distance.py
```

The terrain recipe lives in `src/environment/terrain.py` so placement and offline export share exactly the same visual surface. It does not define the Simulation surface. Preserve original road-edge vertices and collidable prop contact points when editing. Re-export terrain and rebake shoreline together. Local `.blend1` undo backups are ignored, not shipped.
