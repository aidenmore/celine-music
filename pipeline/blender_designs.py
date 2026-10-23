"""
blender_designs.py - Procedural 3D artwork for the release, run inside Blender.

    blender -b -P blender_designs.py -- <mode> <outdir>

modes:  heroes    - four large 3D design renders + .blend files
        covers    - one procedural cover per song
        all       - both

Everything is generated from scratch (no external assets) and rendered with
Cycles on the CPU.
"""
import bpy
import math
import os
import random
import struct
import sys
import wave

# --------------------------------------------------------------- utilities --
def clear_scene():
    bpy.ops.wm.read_factory_settings(use_empty=True)
    for coll in (bpy.data.objects, bpy.data.meshes, bpy.data.materials,
                 bpy.data.lights, bpy.data.cameras, bpy.data.images):
        for item in list(coll):
            try:
                coll.remove(item)
            except Exception:
                pass


def set_input(node, name, value):
    try:
        node.inputs[name].default_value = value
    except Exception:
        pass


def principled(name, base=(0.8, 0.8, 0.8, 1.0), metallic=0.0, roughness=0.4,
               emission=None, emission_strength=0.0, coat=0.0, ior=1.45):
    mat = bpy.data.materials.new(name)
    mat.use_nodes = True
    bsdf = mat.node_tree.nodes.get("Principled BSDF")
    if bsdf:
        set_input(bsdf, "Base Color", base)
        set_input(bsdf, "Metallic", metallic)
        set_input(bsdf, "Roughness", roughness)
        set_input(bsdf, "Coat Weight", coat)
        set_input(bsdf, "IOR", ior)
        if emission is not None:
            set_input(bsdf, "Emission Color", (*emission, 1.0))
            set_input(bsdf, "Emission Strength", emission_strength)
    return mat


def add_area(name, loc, energy, color=(1, 1, 1), size=4.0, rot=(0, 0, 0)):
    data = bpy.data.lights.new(name, type="AREA")
    data.energy = energy
    data.color = color
    data.size = size
    ob = bpy.data.objects.new(name, data)
    ob.location = loc
    ob.rotation_euler = rot
    bpy.context.collection.objects.link(ob)
    return ob


def add_camera(name, loc, look_at=(0, 0, 0), lens=50.0, ortho=None):
    data = bpy.data.cameras.new(name)
    data.lens = lens
    if ortho:
        data.type = "ORTHO"
        data.ortho_scale = ortho
    ob = bpy.data.objects.new(name, data)
    ob.location = loc
    bpy.context.collection.objects.link(ob)
    # point at target
    import mathutils
    d = mathutils.Vector(look_at) - mathutils.Vector(loc)
    ob.rotation_euler = d.to_track_quat("-Z", "Y").to_euler()
    return ob


def setup_world(top=(0.02, 0.02, 0.05), bottom=(0.005, 0.005, 0.01), strength=1.0):
    world = bpy.data.worlds.new("World")
    bpy.context.scene.world = world
    world.use_nodes = True
    nt = world.node_tree
    nt.nodes.clear()
    out = nt.nodes.new("ShaderNodeOutputWorld")
    bg = nt.nodes.new("ShaderNodeBackground")
    grad = nt.nodes.new("ShaderNodeTexGradient")
    ramp = nt.nodes.new("ShaderNodeValToRGB")
    mapn = nt.nodes.new("ShaderNodeMapping")
    tex = nt.nodes.new("ShaderNodeTexCoord")
    mapn.inputs["Rotation"].default_value = (math.radians(90), 0, 0)
    ramp.color_ramp.elements[0].color = (*bottom, 1)
    ramp.color_ramp.elements[1].color = (*top, 1)
    nt.links.new(tex.outputs["Generated"], mapn.inputs["Vector"])
    nt.links.new(mapn.outputs["Vector"], grad.inputs["Vector"])
    nt.links.new(grad.outputs["Fac"], ramp.inputs["Fac"])
    nt.links.new(ramp.outputs["Color"], bg.inputs["Color"])
    bg.inputs["Strength"].default_value = strength
    nt.links.new(bg.outputs["Background"], out.inputs["Surface"])


def setup_cycles(samples=64, res=(900, 900), use_denoise=True):
    sc = bpy.context.scene
    sc.render.engine = "CYCLES"
    sc.cycles.device = "CPU"
    sc.cycles.samples = samples
    sc.cycles.use_denoising = use_denoise
    sc.cycles.max_bounces = 6
    sc.cycles.diffuse_bounces = 3
    sc.cycles.glossy_bounces = 3
    sc.cycles.transmission_bounces = 4
    sc.render.resolution_x, sc.render.resolution_y = res
    sc.render.resolution_percentage = 100
    sc.render.film_transparent = False
    vt_names = [v.identifier for v in
                sc.view_settings.bl_rna.properties["view_transform"].enum_items]
    for want in ("AgX", "Filmic", "Standard"):
        if want in vt_names:
            sc.view_settings.view_transform = want
            break
    sc.view_settings.look = "None"
    return sc


def render_to(path, sc):
    os.makedirs(os.path.dirname(path), exist_ok=True)
    sc.render.filepath = path
    sc.render.image_settings.file_format = "PNG"
    sc.render.image_settings.color_mode = "RGBA"
    bpy.ops.render.render(write_still=True)
    print("RENDERED", path, flush=True)


def add_text(name, body, size, loc, rot=(0, 0, 0), mat=None, align="CENTER"):
    cu = bpy.data.curves.new(name, type="FONT")
    cu.body = body
    cu.size = size
    cu.align_x = align
    cu.align_y = "CENTER"
    cu.extrude = 0.004
    ob = bpy.data.objects.new(name, cu)
    ob.location = loc
    ob.rotation_euler = rot
    if mat:
        ob.data.materials.append(mat)
    bpy.context.collection.objects.link(ob)
    return ob


def read_envelope(wav_path, buckets=220):
    """Return a normalised amplitude envelope from a wav file."""
    try:
        with wave.open(wav_path, "rb") as w:
            n = w.getnframes()
            sr = w.getframerate()
            raw = w.readframes(n)
        ch = w.getnchannels() if hasattr(w, "getnchannels") else 2
    except Exception:
        return None
    import array
    a = array.array("h")
    a.frombytes(raw[:len(raw) // 2 * 2])
    if not a:
        return None
    step = max(1, len(a) // buckets)
    env = []
    for i in range(0, len(a) - step, step):
        seg = a[i:i + step]
        env.append(max(abs(v) for v in seg) / 32768.0)
    m = max(env) or 1.0
    return [v / m for v in env]


# ============================================================== HERO 1 ======
def hero_wave_sculpture(outdir, name="01_Wave_Sculpture"):
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


# ============================================================== HERO 2 ======
def hero_deck_console(outdir, name="02_Deck_Console"):
    """A DJ-style console: decks, platters, faders, emissive pads."""
    clear_scene()
    sc = setup_cycles(samples=100, res=(1000, 1000))
    setup_world((0.02, 0.03, 0.05), (0.004, 0.006, 0.01), 1.0)

    body = principled("Body", (0.035, 0.035, 0.04, 1.0), metallic=0.55,
                      roughness=0.38)
    deck = principled("Deck", (0.10, 0.10, 0.12, 1.0), metallic=0.7, roughness=0.25)
    metal = principled("Metal", (0.6, 0.6, 0.65, 1.0), metallic=1.0, roughness=0.22)
    glow_a = principled("GlowA", (0, 0, 0, 1.0), roughness=0.4,
                        emission=(0.1, 0.9, 1.0), emission_strength=9.0)
    glow_b = principled("GlowB", (0, 0, 0, 1.0), roughness=0.4,
                        emission=(1.0, 0.25, 0.55), emission_strength=9.0)

    def box(loc, scale, mat, bev=0.02):
        bpy.ops.mesh.primitive_cube_add(size=1, location=loc)
        ob = bpy.context.active_object
        ob.scale = scale
        bpy.ops.object.transform_apply(location=False, rotation=False, scale=True)
        ob.data.materials.append(mat)
        b = ob.modifiers.new("Bevel", "BEVEL")
        b.width = bev
        b.segments = 3
        return ob

    def cyl(loc, r, d, mat, verts=64):
        bpy.ops.mesh.primitive_cylinder_add(radius=r, depth=d, location=loc)
        ob = bpy.context.active_object
        ob.data.materials.append(mat)
        bpy.ops.object.shade_smooth()
        return ob

    # table
    box((0, 0, 0.35), (5.4, 3.0, 0.16), body, 0.04)
    # decks
    for sx in (-1, 1):
        x = sx * 1.62
        box((x, 0, 0.46), (1.9, 2.2, 0.10), deck, 0.02)
        cyl((x, 0.35, 0.52), 0.58, 0.05, metal)
        cyl((x, 0.35, 0.55), 0.20, 0.06, glow_a)
        # fader
        box((x + 0.62, -0.55, 0.54), (0.10, 0.85, 0.04), metal, 0.005)
        box((x + 0.62, -0.55 + 0.18, 0.58), (0.16, 0.13, 0.07), glow_b, 0.01)
        # knobs
        for i in range(4):
            cyl((x - 0.72 + i * 0.32, -0.62, 0.55), 0.075, 0.09, metal, 32)
    # mixer
    box((0, 0, 0.47), (1.1, 2.2, 0.12), deck, 0.02)
    for i in range(4):
        x = -0.38 + i * 0.25
        box((x, 0.1, 0.56), (0.045, 0.9, 0.05), metal, 0.004)
        box((x, 0.1 + (0.2 if i % 2 else -0.15), 0.60), (0.13, 0.10, 0.06),
            glow_b if i % 2 else glow_a, 0.008)
    # pad buttons
    for r in range(3):
        for c in range(4):
            bpy.ops.mesh.primitive_cube_add(size=1,
                                            location=(-1.95 + c * 0.22, 0.72 - r * 0.20, 0.53))
            ob = bpy.context.active_object
            ob.scale = (0.15, 0.13, 0.05)
            bpy.ops.object.transform_apply(location=False, rotation=False, scale=True)
            ob.data.materials.append(glow_a if (r + c) % 2 else glow_b)

    bpy.ops.mesh.primitive_plane_add(size=30, location=(0, 0, 0))
    bpy.context.active_object.data.materials.append(
        principled("Floor", (0.015, 0.015, 0.02, 1.0), metallic=0.4, roughness=0.2))

    add_area("Key", (2.6, -3.0, 3.6), 1400, (0.85, 0.9, 1.0), 4.0,
             (math.radians(48), 0, math.radians(40)))
    add_area("Rim", (-3.2, 2.6, 2.2), 900, (1.0, 0.3, 0.6), 3.0,
             (math.radians(68), 0, math.radians(-130)))
    add_area("Top", (0, 0, 4.2), 600, (0.4, 0.8, 1.0), 4.0)

    add_camera("Cam", (0, -5.6, 3.5), (0, 0, 0.55), lens=48)
    render_to(os.path.join(outdir, name + ".png"), sc)
    bpy.ops.wm.save_as_mainfile(filepath=os.path.join(outdir, name + ".blend"))


# ============================================================== HERO 3 ======
def hero_speaker_stack(outdir, name="03_Speaker_Stack"):
    """Stacked PA cabinets with emissive driver rings."""
    clear_scene()
    sc = setup_cycles(samples=100, res=(1000, 1100))
    setup_world((0.015, 0.02, 0.035), (0.003, 0.004, 0.008), 1.0)

    cabinet = principled("Cabinet", (0.03, 0.03, 0.033, 1.0), metallic=0.15,
                          roughness=0.62)
    cone = principled("Cone", (0.012, 0.012, 0.014, 1.0), metallic=0.2,
                      roughness=0.8)
    ring = principled("Ring", (0, 0, 0, 1.0), roughness=0.3,
                      emission=(1.0, 0.18, 0.45), emission_strength=14.0)
    ring2 = principled("Ring2", (0, 0, 0, 1.0), roughness=0.3,
                       emission=(0.15, 0.85, 1.0), emission_strength=12.0)

    def box(loc, scale, mat, bev=0.03):
        bpy.ops.mesh.primitive_cube_add(size=1, location=loc)
        ob = bpy.context.active_object
        ob.scale = scale
        bpy.ops.object.transform_apply(location=False, rotation=False, scale=True)
        ob.data.materials.append(mat)
        b = ob.modifiers.new("Bevel", "BEVEL")
        b.width = bev
        b.segments = 3
        return ob

    def torus(loc, major, minor, mat, rot=(math.radians(90), 0, 0)):
        bpy.ops.mesh.primitive_torus_add(major_radius=major, minor_radius=minor,
                                         major_segments=64, minor_segments=18,
                                         location=loc, rotation=rot)
        ob = bpy.context.active_object
        ob.data.materials.append(mat)
        bpy.ops.object.shade_smooth()
        return ob

    def cone_obj(loc, r, depth, mat):
        bpy.ops.mesh.primitive_cone_add(radius1=r, radius2=r * 0.25,
                                        depth=depth, location=loc,
                                        rotation=(math.radians(90), 0, 0))
        ob = bpy.context.active_object
        ob.data.materials.append(mat)
        bpy.ops.object.shade_smooth()
        return ob

    z = 0.0
    heights = [2.0, 1.5, 1.1]
    for i, h in enumerate(heights):
        box((0, 0, z + h / 2), (2.6, 2.0, h), cabinet, 0.04)
        # drivers
        torus((0, -1.02, z + h * 0.62), 0.48, 0.045, ring if i % 2 == 0 else ring2)
        cone_obj((0, -0.98, z + h * 0.62), 0.46, 0.22, cone)
        torus((0, -1.02, z + h * 0.26), 0.26, 0.035, ring2 if i % 2 == 0 else ring)
        cone_obj((0, -0.98, z + h * 0.26), 0.25, 0.16, cone)
        # handle
        box((1.32, 0, z + h * 0.55), (0.06, 0.5, 0.12), cabinet, 0.02)
        z += h + 0.03

    bpy.ops.mesh.primitive_plane_add(size=34, location=(0, 0, -0.01))
    bpy.context.active_object.data.materials.append(
        principled("Floor", (0.012, 0.012, 0.016, 1.0), metallic=0.35, roughness=0.28))

    add_area("Key", (3.4, -3.2, 3.2), 1500, (1.0, 0.75, 0.85), 4.0,
             (math.radians(50), 0, math.radians(45)))
    add_area("Rim", (-3.4, 1.8, 3.0), 1100, (0.4, 0.7, 1.0), 3.0,
             (math.radians(62), 0, math.radians(-125)))
    add_area("Under", (0, -1.0, 0.12), 300, (1.0, 0.2, 0.5), 2.0,
             (math.radians(90), 0, 0))

    add_camera("Cam", (0.3, -7.4, 2.9), (0, 0, 2.3), lens=62)
    render_to(os.path.join(outdir, name + ".png"), sc)
    bpy.ops.wm.save_as_mainfile(filepath=os.path.join(outdir, name + ".blend"))


# ============================================================== HERO 4 ======
def hero_waveform_ribbon(outdir, wav=None, name="04_Waveform_Ribbon"):
    """A metal ribbon that traces the actual rendered waveform of a track."""
    clear_scene()
    sc = setup_cycles(samples=110, res=(1000, 700))
    setup_world((0.02, 0.025, 0.04), (0.003, 0.004, 0.007), 1.0)

    env = read_envelope(wav, 300) if wav and os.path.exists(wav) else None
    if env is None:
        env = [0.3 + 0.7 * abs(math.sin(i * 0.11)) * (0.4 + 0.6 *
                 abs(math.sin(i * 0.013))) for i in range(300)]

    N = len(env)
    verts, faces = [], []
    for i, a in enumerate(env):
        t = i / (N - 1)
        x = (t - 0.5) * 8.0
        y = math.sin(t * math.pi * 3.0) * 0.55
        z = 1.6 + a * 1.7
        w = 0.05 + a * 0.12
        verts.append((x, y - w, z))
        verts.append((x, y + w, z))
    for i in range(N - 1):
        a0 = i * 2
        faces.append((a0, a0 + 1, a0 + 3, a0 + 2))
    mesh = bpy.data.meshes.new("Ribbon")
    mesh.from_pydata(verts, [], faces)
    mesh.update()
    ob = bpy.data.objects.new("WaveformRibbon", mesh)
    bpy.context.collection.objects.link(ob)
    sol = ob.modifiers.new("Solidify", "SOLIDIFY")
    sol.thickness = 0.045
    bpy.ops.object.select_all(action="DESELECT")
    ob.select_set(True)
    bpy.context.view_layer.objects.active = ob
    bpy.ops.object.shade_smooth()
    ob.data.materials.append(principled("RibbonMetal", (0.55, 0.57, 0.62, 1.0),
                                         metallic=0.95, roughness=0.16, coat=0.5))

    bpy.ops.mesh.primitive_plane_add(size=30, location=(0, 0, 0))
    bpy.context.active_object.data.materials.append(
        principled("Floor", (0.015, 0.016, 0.02, 1.0), metallic=0.4, roughness=0.22))

    add_area("Key", (0, -3.6, 4.6), 1800, (0.9, 0.95, 1.0), 6.0,
             (math.radians(30), 0, 0))
    add_area("Side1", (-4.5, -1.5, 2.4), 900, (1.0, 0.35, 0.6), 3.0,
             (math.radians(72), 0, math.radians(-110)))
    add_area("Side2", (4.5, -1.0, 2.0), 800, (0.3, 0.7, 1.0), 3.0,
             (math.radians(75), 0, math.radians(115)))

    add_camera("Cam", (0, -6.0, 2.6), (0, 0, 1.7), lens=52)
    render_to(os.path.join(outdir, name + ".png"), sc)
    bpy.ops.wm.save_as_mainfile(filepath=os.path.join(outdir, name + ".blend"))


# ============================================================== COVERS =====
PALETTES = [
    ((0.98, 0.16, 0.52), (0.25, 0.05, 0.45), "Neon Pink"),
    ((0.15, 0.95, 0.95), (0.02, 0.18, 0.40), "Cyan Ice"),
    ((1.00, 0.62, 0.10), (0.45, 0.10, 0.02), "Amber Burn"),
    ((0.55, 0.20, 1.00), (0.08, 0.03, 0.32), "Violet Storm"),
    ((0.20, 1.00, 0.55), (0.01, 0.22, 0.16), "Acid Lime"),
    ((1.00, 0.20, 0.20), (0.20, 0.02, 0.04), "Blood Red"),
    ((0.95, 0.95, 1.00), (0.15, 0.16, 0.30), "Chrome White"),
    ((1.00, 0.40, 0.85), (0.30, 0.02, 0.20), "Hot Magenta"),
    ((0.10, 0.55, 1.00), (0.01, 0.08, 0.28), "Deep Azure"),
    ((1.00, 0.85, 0.25), (0.35, 0.18, 0.02), "Gold Rush"),
]


def make_cover(outdir, title, genre, idx, wav=None, size=640, samples=28):
    clear_scene()
    sc = setup_cycles(samples=samples, res=(size, size))
    glow, deep, gname = PALETTES[idx % len(PALETTES)]
    setup_world((deep[0] * 0.7, deep[1] * 0.7, deep[2] * 0.9),
                (deep[0] * 0.15, deep[1] * 0.15, deep[2] * 0.25), 1.2)

    rnd = random.Random(idx * 977 + 13)
    glow_mat = principled("Glow", (0, 0, 0, 1.0), roughness=0.35,
                          emission=glow, emission_strength=12.0)
    body_mat = principled("Body", (deep[0] * 0.5, deep[1] * 0.5, deep[2] * 0.5, 1.0),
                          metallic=0.7, roughness=0.3)

    # A ring of bars driven by the track envelope (or a synthetic one)
    env = read_envelope(wav, 120) if wav and os.path.exists(wav) else None
    if env is None:
        env = [0.25 + 0.75 * abs(math.sin(i * 0.21 + idx)) for i in range(60)]
    N = min(60, len(env))
    step = max(1, len(env) // N)
    env = env[::step][:N]

    for i, a in enumerate(env):
        ang = (i / N) * math.tau
        r = 1.55
        h = 0.18 + a * 1.9
        x = math.cos(ang) * r
        y = math.sin(ang) * r
        bpy.ops.mesh.primitive_cube_add(size=1, location=(x, y, h / 2))
        ob = bpy.context.active_object
        ob.scale = (0.12, 0.12, h)
        bpy.ops.object.transform_apply(location=False, rotation=False, scale=True)
        ob.rotation_euler = (0, 0, ang)
        ob.data.materials.append(glow_mat if i % 3 == 0 else body_mat)

    # central glowing disc
    bpy.ops.mesh.primitive_cylinder_add(radius=1.05, depth=0.10, location=(0, 0, 0.05))
    disc = bpy.context.active_object
    disc.data.materials.append(principled("Disc", (0, 0, 0, 1.0), roughness=0.3,
                                          emission=glow, emission_strength=4.0))
    bpy.ops.mesh.primitive_torus_add(major_radius=1.12, minor_radius=0.035,
                                     major_segments=96, minor_segments=14,
                                     location=(0, 0, 0.10))
    tr = bpy.context.active_object
    tr.data.materials.append(glow_mat)
    bpy.ops.object.shade_smooth()

    bpy.ops.mesh.primitive_plane_add(size=24, location=(0, 0, -0.01))
    bpy.context.active_object.data.materials.append(
        principled("Floor", (deep[0] * 0.4, deep[1] * 0.4, deep[2] * 0.4, 1.0),
                   metallic=0.45, roughness=0.25))

    # text plate
    add_text("Title", title.upper(), 0.30, (0, -0.55, 2.55), (0, 0, 0),
             principled("Text", (0.02, 0.02, 0.02, 1.0), roughness=0.5,
                        emission=(0.95, 0.95, 0.98, 1.0), emission_strength=3.0))
    add_text("Genre", genre.upper(), 0.16, (0, -0.55, 2.22), (0, 0, 0),
             principled("Text2", (0.02, 0.02, 0.02, 1.0), roughness=0.5,
                        emission=glow, emission_strength=2.2))

    add_area("Key", (3.0, -3.0, 4.0), 1300, glow, 4.0,
             (math.radians(48), 0, math.radians(42)))
    add_area("Rim", (-3.2, 2.0, 2.4), 800, (0.4, 0.6, 1.0), 3.0,
             (math.radians(70), 0, math.radians(-120)))

    add_camera("Cam", (0, -6.2, 3.4), (0, 0, 1.05), lens=52)
    safe = title.replace(" ", "_").replace("'", "")
    render_to(os.path.join(outdir, f"cover_{safe}.png"), sc)


# ================================================================= main =====
def main():
    argv = sys.argv[sys.argv.index("--") + 1:] if "--" in sys.argv else ["all", "."]
    mode = argv[0]
    outdir = argv[1] if len(argv) > 1 else os.getcwd()
    outdir = os.path.abspath(outdir)
    os.makedirs(outdir, exist_ok=True)

    songs_dir = os.path.join(os.path.dirname(outdir), "songs")
    renders_dir = os.path.join(os.path.dirname(outdir), "renders")

    if mode in ("heroes", "all"):
        hero_wave_sculpture(outdir)
        hero_deck_console(outdir)
        hero_speaker_stack(outdir)
        wav = None
        cand = os.path.join(renders_dir, "01_Neon_Drift.wav")
        if os.path.exists(cand):
            wav = cand
        hero_waveform_ribbon(outdir, wav)

    if mode in ("covers", "all"):
        titles = []
        if os.path.isdir(songs_dir):
            for f in sorted(os.listdir(songs_dir)):
                if f.endswith(".mp3"):
                    titles.append(os.path.splitext(f)[0].replace("_", " "))
        if not titles:
            titles = [f"Track {i+1}" for i in range(20)]
        genres = ["Future House", "Stutter House", "Phonk", "Rave Trance",
                  "Eurodance", "Future Bass", "Deep House", "Electro House",
                  "Techno", "Melodic Techno", "Drum & Bass", "UK Garage",
                  "Moombahton", "Hard Techno", "Uplifting Trance", "Acid Techno",
                  "Progressive House", "Melodic House", "Jungle", "Big Room"]
        for i, t in enumerate(titles):
            wav = os.path.join(renders_dir, t.replace(" ", "_") + ".wav")
            make_cover(outdir, t, genres[i % len(genres)], i,
                       wav if os.path.exists(wav) else None)
    print("BLENDER DONE", flush=True)


if __name__ == "__main__":
    main()
