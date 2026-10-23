"""One-shot patch: Blender 5.2 API fixes (no torus-knot op, AgX view transform)."""
import re

P = r"C:\Users\Thinkbook\OneDrive\Celine\scripts\blender_designs.py"
t = open(P, encoding="utf-8").read()

# --- view transform: prefer AgX, fall back to Filmic/Standard ---------------
old_vt = '''    sc.view_settings.view_transform = "Filmic" if "Filmic" in [
        v.name for v in sc.view_settings.bl_rna.properties["view_transform"].enum_items
    ] else "Standard"'''
new_vt = '''    vt_names = [v.identifier for v in
                sc.view_settings.bl_rna.properties["view_transform"].enum_items]
    for want in ("AgX", "Filmic", "Standard"):
        if want in vt_names:
            sc.view_settings.view_transform = want
            break'''
t = t.replace(old_vt, new_vt)

# --- hero 1: rebuild without primitive_torus_knot_add ----------------------
start = t.index("def hero_wave_sculpture(")
end = t.index("# ============================================================== HERO 2 ======")
new_hero = '''def hero_wave_sculpture(outdir, name="01_Wave_Sculpture"):
    """Neon wave sculpture: stacked emissive rings around a glowing core."""
    clear_scene()
    sc = setup_cycles(samples=110, res=(1000, 1000))
    setup_world((0.03, 0.01, 0.06), (0.004, 0.004, 0.01), 1.0)

    skin = principled("NeonSkin", (0.05, 0.02, 0.10, 1.0), metallic=0.85,
                      roughness=0.22, emission=(1.0, 0.12, 0.62),
                      emission_strength=3.0, coat=0.6)
    skin2 = principled("NeonSkin2", (0.03, 0.04, 0.10, 1.0), metallic=0.85,
                       roughness=0.25, emission=(0.20, 0.55, 1.0),
                       emission_strength=2.4, coat=0.6)
    core = principled("Core", (0, 0, 0, 1.0), roughness=0.3,
                      emission=(1.0, 0.55, 0.85), emission_strength=22.0)

    # a stack of torii, each displaced by a different waveform
    for i in range(7):
        rad = 1.05 + i * 0.23
        z = 0.35 + i * 0.33
        bpy.ops.mesh.primitive_torus_add(major_radius=rad, minor_radius=0.115,
                                         major_segments=180, minor_segments=26,
                                         location=(0, 0, z),
                                         rotation=(math.radians(90), 0, 0))
        ob = bpy.context.active_object
        ob.name = f"WaveRing_{i}"
        ob.data.materials.append(skin if i % 2 == 0 else skin2)
        bpy.ops.object.shade_smooth()

        disp = ob.modifiers.new("Wave", "DISPLACE")
        tex = bpy.data.textures.new(f"WaveTex{i}", type="WOOD")
        tex.noise_scale = 0.30 + i * 0.05
        tex.noise_basis = "SIN"
        disp.texture = tex
        disp.strength = 0.16 + i * 0.03
        disp.mid_level = 0.5
        disp.texture_coords = "GLOBAL"
        sol = ob.modifiers.new("Solidify", "SOLIDIFY")
        sol.thickness = 0.045
        sol.offset = 0.0

    bpy.ops.mesh.primitive_ico_sphere_add(radius=0.55, subdivisions=5,
                                          location=(0, 0, 1.55))
    ball = bpy.context.active_object
    ball.name = "Core"
    ball.data.materials.append(core)
    bpy.ops.object.shade_smooth()

    bpy.ops.mesh.primitive_plane_add(size=26, location=(0, 0, 0))
    bpy.context.active_object.data.materials.append(
        principled("Floor", (0.02, 0.02, 0.03, 1.0), metallic=0.25, roughness=0.16))

    add_area("Key", (3.2, -3.4, 4.2), 1600, (1.0, 0.45, 0.75), 5.0,
             (math.radians(45), 0, math.radians(40)))
    add_area("Rim", (-4.0, 2.2, 2.6), 1200, (0.35, 0.6, 1.0), 4.0,
             (math.radians(70), 0, math.radians(-120)))
    add_area("Fill", (0, 4.5, 1.2), 500, (0.6, 0.2, 1.0), 6.0,
             (math.radians(75), 0, math.radians(180)))

    add_camera("Cam", (0, -6.4, 2.9), (0, 0, 1.5), lens=55)
    render_to(os.path.join(outdir, name + ".png"), sc)
    bpy.ops.wm.save_as_mainfile(filepath=os.path.join(outdir, name + ".blend"))


'''
t = t[:start] + new_hero + t[end:]
open(P, "w", encoding="utf-8").write(t)
print("blender script patched")
print("torus_knot remaining:", t.count("torus_knot"))
