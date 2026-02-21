# Blender MCP - AI-Controlled 3D Modeling

## Overview
- **What:** MCP server that lets Claude control Blender via natural language
- **Repo:** [ahujasid/blender-mcp](https://github.com/ahujasid/blender-mcp) (v1.5.5)
- **Local clone:** `C:\Users\scott\blender-mcp\`
- **Blender version:** 4.3 at `C:\Program Files\Blender Foundation\Blender 4.3\`

## Setup (Completed Feb 18, 2026)
- MCP server registered in both Claude Code and Claude Desktop configs
- Telemetry disabled via `DISABLE_TELEMETRY=true` env var
- Addon: `C:\Users\scott\blender-mcp\addon.py` installed in Blender
- Connection: Blender sidebar (N key) > BlenderMCP tab > "Connect to Claude"
- Socket-based: Blender addon listens on localhost:9876, MCP server connects to it

## CRITICAL LESSONS LEARNED (Feb 18, 2026)

### Save Often with Timestamps
- **ALWAYS save after every significant operation** using timestamped filenames
- Pattern: `bpy.ops.wm.save_as_mainfile(filepath=f"C:\\Users\\scott\\project_{timestamp}.blend")`
- Blender crashes frequently during complex mesh operations (undo, BMesh manipulation)
- Connection drops silently — operations in flight are lost
- Save BEFORE and AFTER risky operations (boolean, undo, large deletes)

### Blender 4.3 API Changes
- `mesh.use_auto_smooth` REMOVED in Blender 4.x — skip it, auto smooth handled differently
- `bpy.ops.mesh.delete(type='FACE')` not `'FACES'` — enum values are singular

### BMesh Gotchas
- **Index invalidation**: After `remove_doubles` or `delete`, MUST call `ensure_lookup_table()` before accessing by index
- **Don't mix BMesh ops and bpy.ops in same edit session** — use one or the other
- **Prefer `bpy.ops.mesh.*` operators** over `bmesh.ops.*` for safety — they handle index updates internally
- **Complex multi-step BMesh**: Split into separate `execute_blender_code` calls to avoid stale references

### Boolean Operation Artifacts
- Boolean DIFFERENCE creates: floating islands, degenerate faces, opposite-normal fins, flat cap remnants
- **Cleanup sequence**: merge doubles (0.0001) → dissolve degenerate → delete loose → BFS island removal
- **Fin detection**: Find edges where `len(link_faces)==2` and the two face normals dot product < -0.7
- **Protruding geometry detection**: Compare vertex distance from axis against dome profile radius
- **NEVER delete internal hole caps** unless you want open holes — removing caps exposes messy interior
- For vent holes: delete faces protruding BEYOND expected surface, leave flush/interior faces

### Connection Stability
- `bpy.ops.ed.undo()` can crash the connection — avoid multi-undo from MCP
- If connection drops: user must re-enable addon in Blender (N > BlenderMCP > Connect)
- After Blender restart: must reinstall addon if not in startup file
- Only ONE MCP client at a time (Claude Code OR Desktop, not both)

### Camera & Viewport
- Small models (< 200mm) need camera positioned very close — calculate from model bounds
- Set `view_distance` proportional to model size (0.15-0.25 for ~150mm models)
- Material preview: `space.shading.type = 'MATERIAL'`; wireframe: `'WIREFRAME'`

### Texture Workflow
- Scene-style AI textures don't work as surface materials on 3D geometry
- Use TILEABLE surface textures (moss, stone, plaster, wood) with height-zoned materials
- Height zoning: Object coordinates → Separate XYZ → Z for blend position
- Noise texture (scale=80, detail=6) for organic transitions between zones

## Capabilities
- Create, modify, delete 3D objects via natural language
- Apply/modify materials and colors
- Execute arbitrary Python (`bpy`) code in Blender
- Scene inspection and manipulation
- Poly Haven asset integration (models, textures, HDRIs)
- Hyper3D Rodin AI-generated 3D models
- Hunyuan3D support
- Sketchfab model search/download
- **STL export** via `bpy.ops.export_mesh.stl()` (native Blender, not explicit in MCP but works via code execution)

## Export Formats
- STL (3D printing) — `bpy.ops.export_mesh.stl(filepath="path.stl")`
- OBJ — `bpy.ops.wm.obj_export(filepath="path.obj")`
- FBX — `bpy.ops.export_scene.fbx(filepath="path.fbx")`
- GLB/GLTF — `bpy.ops.export_scene.gltf(filepath="path.glb")`

## Key MCP Tools
- `get_scene_info` — inspect current scene
- `get_viewport_screenshot` — visual check (max_size=800 for detail)
- `execute_blender_code` — run arbitrary Python in Blender (most powerful)
- `get_object_info` — detailed object inspection
- Poly Haven, Sketchfab, Hyper3D integrations available

## Workflow for 3D Printing
1. Design model in Blender via Claude MCP commands
2. Save frequently with timestamps
3. Export as STL: `bpy.ops.export_mesh.stl(filepath="C:/Users/scott/path/model.stl")`
4. Slice in Cura or PrusaSlicer
5. Print on 3D printer

## Advanced Cleanup Techniques (Feb 19, 2026)

### Interior Face Removal
- `bpy.ops.mesh.select_interior_faces()` finds hidden internal geometry from booleans
- Removed 369 interior faces in one pass — cleans up vent tube walls showing through dome
- Always follow with `normals_make_consistent(inside=False)`

### Dome Radius Profiling for Protrusion Detection
- Build Z→radius map using 85-90th percentile of vertex radii at each Z level
- Delete vertices where R > expected_R + margin (2-3mm)
- Effective for removing filled-vent bumps that create "old chimney" appearance
- Use 1mm Z-buckets for smooth profile interpolation

### Protruding Door Frame Solution
- Problem: Dome curves away from vertical facade plate at base → door bottom absorbed
- Fix: Create annular cylinder (portal frame) extending 4mm past dome's most forward Y
- Door portal: inner R=15mm, outer R=19.5mm, depth=13mm, front Y=-69mm
- Must be further forward than dome base (Y=-64.7mm) to show full circle

### Vent Holes for Enclosures
- Mac Mini needs airflow: exhaust (top/back) + intake (bottom/back)
- Boolean DIFFERENCE with cylinders pointed in Y direction for clean round holes
- Exhaust: 3x R=6mm holes at Z=55-58mm (hot air rises)
- Intake: 4x R=5mm holes at Z=13-14mm (cool air enters)
- Position cutters at dome back surface Y with 30mm depth for clean cut-through

## Current Project: Mac Mini OpenClaw House (Feb 18-19, 2026)
- **Concept:** Decorative 3D-printed fairy/hobbit house enclosure for Mac Mini
- **Mac Mini M4 dimensions:** 127mm x 127mm x 50.8mm (5" square, 2" tall)
- **Two-piece design:** ShellBody (dome) + FacadePlate (snap-on front)
- **Interior clearance:** 131x131x54mm
- **Latest save:** `hobbit_house_20260219_103507.blend`
- **ShellBody:** 15,170 verts — dome + chimney + 7 vent holes (3 exhaust, 4 intake)
- **FacadePlate:** 3,204 verts — curved plate + protruding door/window portals + frames
- **Textures:** Height-zoned material (moss roof, plaster walls) + ComfyUI SDXL tileable
- **Remaining:** Texture blob above door, small base artifacts, research better texturing (StableGen)

## Voice Transcription
- "Blender MCP" may transcribe as "blender MCP" or "blender M-C-P"
- "STL" may transcribe as "STL" or "S-T-L" or "estal"
