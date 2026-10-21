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
- **Rearrange the furniture** (the Furniture tab): drag a piece in from the catalog — pictured from the model itself, with IKEA article numbers — or click it to put it in front of you. Pick up any loose piece to move it: it snaps to a 10 cm grid and to the walls, and never goes through walls, built-ins or other furniture. Scroll while holding it (or `,` `.`, or Turn) to rotate it; Remove or Delete takes it out; Ctrl Z undoes. The light follows: the spot a piece left takes the "empty room" bake (walls, floor, rugs, built-ins), its own baked floor shadow goes with it (the floor's lightmap is a plain top view, so the shadow is read where it stood), and it takes the brightness of the floor where it now stands. Everything that did not move keeps its exact bake. Built-ins, curtains and the floor lamps stay put.
- **Doors and curtains**: click a door to swing it shut (you can't walk through a shut door) and again to open it; click a curtain to draw the sheers across the window or gather them to the side. Drawn sheers glow with the daylight behind them and the room's daylight drops; they move in a light breeze.
- **Moods**: six ready-made combinations of floor, walls, fabric and wood — one click for this room, or tick "every room".
- **Moodboard** (top left, or M): every room's choices side by side, the IKEA pieces in the room you are in with their article numbers, and a link that keeps everything — picks, time, lighting scene, furniture, doors and curtains, and where you stand. **Shopping list** prints (or saves as a PDF) every IKEA piece per room, counted from the furniture as it stands now.
- **Measurements**: while a piece is selected, lines on the floor give the distance from each side to the nearest wall, built-in or other piece.
- **Phones**: one panel at a time from the bar at the bottom.

## Files

| | |
|---|---|
| `index.html`, `css/`, `js/mood.js` | the page |
| `js/world.js`, `js/data.js`, `js/build.js`, `js/shading.js` | the city and bay outside; the plan data (from the DXF) |
| `mood/*.gltf`, `*.bin`, `tex/` | the three parts of the model |
| `mood/lm/`, `mood/lightmaps.json` | the baked light (WebP; lamp groups three to a map) |
| `mood/pieces.json`, `js/furniture.js` | which objects form a movable piece (from `blender/piece_tag.py`), and the furniture editor |
| `js/openings.js` | doors and curtains: hinges and rails from the plan data, the daylight behind drawn sheers |
| `mood/texmap.json` | Blender's object-space texture mapping per material (floors, oak, rugs, fabrics), which glTF can't carry — the page reproduces it |
| `design/` | the Japandi scheme and the lighting plan (circuits, fittings, scenes) |
| `blender/*.py`, `tools/` | the pipeline that builds, bakes and packs it |

## Before a deploy

```
node tools/check.mjs        # needs: npm i playwright (in tools/)
```

It checks that every file the page loads carries the same release version (`?v=` in `index.html` and the imports in `js/mood.js`) and that the version was raised if anything changed since the last push. Then it loads the page in headless Chromium with a piece moved, a door shut and the sheers drawn, and makes sure no shader needs more than the 16 textures most graphics cards and phones allow (Chrome on Windows refuses such a shader, and that part of the flat is simply not drawn), and that the console stays clean.

## Rebuild

Needs Blender 5.2 with an NVIDIA GPU, Python 3 with `numpy scipy pillow oidn`, Node with `@gltf-transform/core @gltf-transform/extensions @gltf-transform/functions meshoptimizer sharp`. The `.blend` files, IKEA model downloads and Blender textures are not in the repository (too large).

```
blender (live)  → exec build_scene.py, bedrooms.py, lighting_build.py      # the furnished, lit scene
blender (live)  → exec mood_prep2.py                                        # web copies + lightmap UVs → blender/dira_mood2.blend
blender (live)  → exec texmap_export.py                                     # mood/texmap.json
blender -b dira_mood2.blend -P floor_merge.py                               # one floor for the whole flat, shell atlas packed again
blender -b dira_mood2.blend -P piece_tag.py                                 # movable pieces → mood/pieces.json
blender\mood_bake2.cmd                                                      # export + bake, ~4 h on a laptop RTX 4060
blender -b dira_mood2.blend -P mood_bake2.py -- 128 160 empty,<groups>      # the "empty room" bake (shell, built-ins, rugs), ~3 h
MOOD_OUT=. python3 tools/mood_pack.py                                       # denoise (OIDN) + pack → mood/lm/*.webp, mood/lightmaps.json
node tools/mood_glb.mjs mood/v2/shell_raw.glb mood/shell.gltf               # and living, rooms
```
