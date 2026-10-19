# דירה בקומה 13 · Flat 13

A live 3D model of the flat — a 13th-floor apartment in Haifa, Japandi interior with IKEA furniture — that you walk through and restyle in the browser. Built with three.js; the light is baked in Blender Cycles.

## Run it

Any static web server from the repository root, for example:

```
python -m http.server 8000
```

then open `http://localhost:8000/`. (Opening `index.html` straight from disk does not work: the browser blocks the model files.)

## What it does

- **The whole flat, loaded in three parts**: the shell (walls, floors, ceilings, windows), then the living room, entry, kitchen and balcony — the page opens here — and the bedrooms, corridor and bathrooms follow in the background. About 13 MB before the first view, 26 MB in all. Textures are shared files (`mood/tex/`), so one used in several rooms downloads once.
- **Baked light, mixed live**: Cycles baked each light group once — three times of day (morning, midday, dusk sky) and twelve groups of the lighting plan's circuits (entry, walls, media wall, paper lamps, screen, kitchen, corridor + night path, main bedroom, office, teen room, toddler room, balcony). Light adds up linearly, so the time-of-day slider and every scene in `design/lighting.json` (Welcome, Evening, Cooking, Bay view, Film, Bedtime, Night path…) are exact mixes of the bakes. Dim scenes get a little more exposure, the way your eyes adapt.
- **Walk around**: drag to look, click the floor to walk there (a ring shows where you'll stop), arrows / WASD, double-click the overview to step in at that spot. The plan at the bottom right shows where you are; click a room to go there.
- **Style each room**: the samples style the room you are in (they follow you as you walk; or pick a room from the list). Drag a sample onto a wall, floor or piece of furniture in any room, or click it. Wall paint is per room even where one wall is shared by two rooms.
- **Moods**: six ready-made combinations of floor, walls, fabric and wood — one click for this room, or tick "every room".
- **Moodboard** (top left, or M): every room's choices side by side, the IKEA pieces in the room you are in with their article numbers, and a link that keeps everything — picks, time, lighting scene and where you stand.
- **Phones**: one panel at a time from the bar at the bottom.

## Files

| | |
|---|---|
| `index.html`, `css/`, `js/mood.js` | the page |
| `js/world.js`, `js/data.js`, `js/build.js`, `js/shading.js` | the city and bay outside; the plan data (from the DXF) |
| `mood/*.gltf`, `*.bin`, `tex/` | the three parts of the model |
| `mood/lm/`, `mood/lightmaps.json` | the baked light (WebP; lamp groups three to a map) |
| `mood/texmap.json` | Blender's object-space texture mapping per material (floors, oak, rugs, fabrics), which glTF can't carry — the page reproduces it |
| `design/` | the Japandi scheme and the lighting plan (circuits, fittings, scenes) |
| `blender/*.py`, `tools/` | the pipeline that builds, bakes and packs it |

## Rebuild

Needs Blender 5.2 with an NVIDIA GPU, Python 3 with `numpy scipy pillow oidn`, Node with `@gltf-transform/core @gltf-transform/extensions @gltf-transform/functions meshoptimizer sharp`. The `.blend` files, IKEA model downloads and Blender textures are not in the repository (too large).

```
blender (live)  → exec build_scene.py, bedrooms.py, lighting_build.py      # the furnished, lit scene
blender (live)  → exec mood_prep2.py                                        # web copies + lightmap UVs → blender/dira_mood2.blend
blender (live)  → exec texmap_export.py                                     # mood/texmap.json
blender\mood_bake2.cmd                                                      # export + bake, ~4 h on a laptop RTX 4060
MOOD_OUT=. python3 tools/mood_pack.py                                       # denoise (OIDN) + pack → mood/lm/*.webp, mood/lightmaps.json
node tools/mood_glb.mjs mood/v2/shell_raw.glb mood/shell.gltf               # and living, rooms
```
