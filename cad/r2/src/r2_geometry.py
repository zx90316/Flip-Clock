"""FC-R2, newly authored desktop mechanism and support-conscious FDM enclosure.

Millimetres, X axles, +Y front. Canonical leaf extends +Z, front face +Y.
The source fan is an inspection/initial pose, never a simulated gravity result.
Purchased components are explicitly labelled envelopes, not fabrication solids.
"""
from __future__ import annotations
from functools import lru_cache
import json
import math
from pathlib import Path
import sys
from cadgen import build123d as bd, srgb

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT.parent / "src"))
# Pure, independently authored primitives; none of these reads R1 parameters.
from geometry import gear, gear_profile, ring, cylinder_x, place_axial, circle_holes, rounded_polygon, wire_spring, DIGITS

COLORS = {"case": "#ECE7DD", "dark": "#242E35", "flap": "#182228", "ink": "#F4F0DF",
          "M": "#538B89", "H": "#B79460", "steel": "#A6AFB4", "POM": "#D7CDB8", "pcb": "#346447", "belt": "#303333"}


@lru_cache(maxsize=1)
def config():
    return json.loads((ROOT / "parameters.json").read_text(encoding="utf-8"))


def named(shape, name, color="dark"):
    shape.label = name
    shape.color = srgb(COLORS.get(color, color))
    return shape


def group(name, parts):
    return bd.Compound(children=list(parts), label=name)


def sign(b):
    return 1 if b == "H" else -1


def count(b):
    return 24 if b == "H" else 60


def axis_y(b):
    return config()["hour_axis_y"] if b == "H" else 0


def pivot_r(b):
    return config()["hour_pivot_r"] if b == "H" else config()["flap"]["pivot_r"]


def flange_r(b):
    return config()["hour_flange_r"] if b == "H" else config()["flap"]["flange_r"]


def mesh_phase(ca, cb, na, nb, phase_a):
    # Canonical gear +u maps to world -Z, +v to world +Y.
    theta = math.atan2(cb[0] - ca[0], -(cb[1] - ca[1]))
    fa = (na * (theta - math.radians(phase_a)) / (2 * math.pi)) % 1
    return math.degrees(theta + math.pi - ((.5 - fa) % 1) * 2 * math.pi / nb) % (360 / nb)


def hour_train():
    # Three real gear contacts: 60 -> 20 -> 20 -> 40, 1.5:1 speed, reverse.
    p = config(); total = axis_y("H") - p["input_y"]; lo, hi = 0., 35.999
    for _ in range(60):
        h = (lo + hi) / 2
        reach = math.sqrt(48**2 - h**2) + 24 + math.sqrt(36**2 - h**2)
        if reach > total: lo = h
        else: hi = h
    h = (lo + hi) / 2; a = (p["input_y"], p["axis_z"])
    c1 = (a[0] + math.sqrt(48**2 - h**2), a[1] + h); c2 = (c1[0] + 24, c1[1]); out = (axis_y("H"), a[1])
    p1 = mesh_phase(a, c1, 60, 20, 0); p2 = mesh_phase(c1, c2, 20, 20, p1); po = mesh_phase(c2, out, 20, 40, p2)
    return {"centres": [c1, c2], "phases": [p1, p2], "output_phase": po, "speed_ratio": -1.5}


def direction(b):
    # R2 turns both displays front-down: negative input=M, positive input=H.
    return -1 if b == "M" else 1


def rounded_box(w, d, h, r):
    return bd.extrude(bd.RectangleRounded(w, d, r), amount=h / 2, both=True)


def mounting_points():
    return [(x, y) for x in (-88.8, 88.8) for y in (-88, 42)]


def base():
    c = config()["case"]
    shape = bd.Pos(0, -29, c["base_t"] / 2) * rounded_box(c["width"], c["depth"], c["base_t"], c["corner_r"])
    # All screws enter from underneath, leaving the front clean.
    holes = mounting_points() + [(-69, -96), (-69, 18), (69, -96), (69, 39.6)] + [(0, y) for y in (-8, 10.8, 29.6)]
    holes += [(-59, -46), (-59, -26.5)] + [(sign(b) * 52.5, axis_y(b) - 5 + dy) for b in ("M", "H") for dy in (-10, 10)]
    holes += [(12, -96), (28, -96)]
    ht = hour_train(); holes += [(62.8, ht["centres"][0][0] - 11), (62.8, -14)]
    holes += [(sign(b) * 85, axis_y(b) + dy) for b in ("M", "H") for dy in (-10, 10)]
    for x, y in holes:
        shape -= bd.Pos(x, y, 2.4) * bd.Cylinder(1.7, 8)
        shape -= bd.Pos(x, y, 1.3) * bd.Cylinder(3.2, 2.6)
    return named(shape, "A00_single_base", "case")


def hood():
    c = config()["case"]
    height = c["height"] - c["base_t"]
    outer = bd.Pos(0, -29, (120 + 4.8) / 2) * rounded_box(190, 174, height, 12)
    inner = bd.Pos(0, -29, (117.6 + 2) / 2) * rounded_box(185.2, 169.2, 115.6, 9.6)
    shape = outer - inner
    # Separate flat panels eliminate window bridges in the upside-down hood.
    shape -= bd.Pos(0, -29, (117.6 + 2) / 2) * bd.Box(166, 180, 115.6)
    for x, y in mounting_points():
        boss = bd.Pos(x, y, 8.4) * bd.Box(8.4, 9, 7.2)
        s = 1 if x > 0 else -1
        ramp = bd.Polygon((s * 84.6, 12), (s * 93, 12), (s * 93, 20.4), align=None)
        boss += bd.Pos(0, y, 0) * bd.Rot(90, 0, 0) * bd.extrude(ramp, amount=4.5, both=True)
        boss -= bd.Pos(x, y, 8.4) * bd.Cylinder(1.7, 10)
        boss -= bd.Pos(x, y, 6) * bd.extrude(bd.RegularPolygon(3.3, 6), amount=2.8, both=True)
        shape += boss
    # Front/back panel mounting cheeks, receiving captive M3 nuts.
    for x in (-78, 78):
        for y in (45.9, -109.9):
            for z in (15, 90):
                cheek = bd.Pos(x, y, z) * bd.Box(9, 6, 12)
                # Full 45-degree ramps support these inward cheeks when the
                # hood is printed roof-down, including the upper fasteners.
                cheek += bd.Pos(math.copysign(86, x), y, z) * bd.Box(16, 6, 12)
                s = 1 if x > 0 else -1
                ramp = bd.Polygon((s * 73.5, z + 6), (s * 94, z + 6), (s * 94, z + 26.5), align=None)
                cheek += bd.Pos(0, y, 0) * bd.Rot(90, 0, 0) * bd.extrude(ramp, amount=3, both=True)
                cheek -= bd.Pos(x, y, z) * bd.Rot(90, 0, 0) * bd.Cylinder(1.7, 12)
                shape += cheek
    # Trim mounting cheeks to the actual rounded outer skin: no rear-corner
    # tabs protrude beyond the desktop enclosure's curved silhouette.
    return named(shape & outer, "A01_inverted_print_hood", "case")


def panel(front=True):
    y = 56.4 if front else -114.4
    shape = bd.Pos(0, y, 61.2) * bd.Rot(90, 0, 0) * rounded_box(165.2, 112.0, 2.4, 3)
    if front:
        for x in (-24, 24):
            aperture = bd.Pos(x, y, 58) * bd.Rot(90, 0, 0) * rounded_box(36.4, 38.4, 10, 2.4)
            shape -= aperture
        # Retaining-wire bosses sit behind the panel, above the visible halves.
        # Each wire is clamped by two M2 split blocks; the arch is never printed.
    else:
        for x in range(-24, 25, 8):
            shape -= bd.Pos(x, y, 18) * bd.Box(3, 8, 16)
        shape -= bd.Pos(45, y, 15) * bd.Box(12, 8, 6)  # Connector envelope, not a selected USB module.
    for x in (-78, 78):
        for z in (15, 90):
            if front:
                # Hidden screws enter from the rear into an edge-fed captive
                # nut. The front remains an uninterrupted textured surface.
                boss = bd.Pos(x, 52.2, z) * bd.Box(9, 6, 12)
                boss -= bd.Pos(x, 52, z) * bd.Rot(90, 0, 0) * bd.Cylinder(1.7, 6)
                boss -= bd.Pos(x, 52.7, z) * bd.Rot(90, 0, 0) * bd.extrude(bd.RegularPolygon(3.3, 6), amount=1.3, both=True)
                boss -= bd.Pos(x, 52.7, z + 4) * bd.Box(6.6, 2.6, 8)
                shape += boss
            else:
                shape -= bd.Pos(x, y, z) * bd.Rot(90, 0, 0) * bd.Cylinder(1.7, 8)
    if front:
        for cx in (-24, 24):
            for s in (-1, 1):
                x = cx + s * 19
                block = bd.Pos(x, 50.2, 73) * bd.Box(3, 10, 6)
                block -= cylinder_x(.55, 6, x, 47.4, 73)
                shape += block
    return named(shape, "A02_front_panel" if front else "A03_rear_panel", "dark" if front else "case")


def bezel():
    outer = rounded_box(94, 46, 1.8, 5)
    for x in (-24, 24):
        outer -= bd.Pos(x, 0, 0) * rounded_box(36.4, 38.4, 6, 2.4)
    for z in (-4.2, 4.2):
        outer -= bd.Pos(0, z, 0) * bd.Cylinder(1.5, 6)
    return named(bd.Pos(0, 58.5, 58) * bd.Rot(90, 0, 0) * outer, "A04_display_bezel", "dark")


def colon_inlays():
    return [named(bd.Pos(0, 58.5, 58 + z) * bd.Rot(90, 0, 0) * bd.Cylinder(1.4, 1.8), f"A05_colon_{i}", "ink")
            for i, z in enumerate((-4.2, 4.2))]


def side_frame(b):
    p = config(); x = sign(b) * p["frame_x"]; z = p["axis_z"]
    front = axis_y(b); cy = (front - 72) / 2
    shape = bd.Pos(x, cy, 7.2) * bd.Box(6.4, 150 if b == "H" else 128, 4.8)
    for y in (front, -72):
        shape += bd.Pos(x, y, (z + 9.6) / 2) * bd.Box(6.4, 27, z - 9.6)
        shape += cylinder_x(14, 6.4, x, y, z)
        shape -= cylinder_x(11.1, 10, x, y, z)
    shape += bd.Pos(x, cy, z) * bd.Box(6.4, front + 72, 14)
    # Recut after union: the beam must not fill the bearing pockets.
    for y in (front, -72):
        shape -= cylinder_x(11.1, 10, x, y, z)
    for y in (-96, front + 18):
        shape -= bd.Pos(x, y, 8) * bd.Cylinder(1.7, 12)
    return named(shape, "A10_" + b + "_internal_frame", "dark")


def center_frame():
    z = config()["axis_z"]
    shape = bd.Pos(0, 10.8, 7.2) * bd.Box(6, 45.6, 4.8)
    for yy in (0, axis_y("H")):
        shape += bd.Pos(0, yy, (z + 4.8) / 2) * bd.Box(6, 17, z - 4.8)
        shape += cylinder_x(8, 6, 0, yy, z)
        shape -= cylinder_x(6.1, 10, 0, yy, z)
    for y in (-8, 10.8, 29.6):
        shape -= bd.Pos(0, y, 8) * bd.Cylinder(1.7, 12)
    return named(shape, "A11_center_plain_bearing_pedestal", "dark")


def ratchet_profile(b):
    r = config()["ratchet"]; pts = []
    for k in range(r["teeth"]):
        for phase, radius in ((0, r["root_r"]), (.44, r["root_r"]), (.54, r["tip_r"]), (.90, r["tip_r"])):
            a = direction(b) * (2 * math.pi * (k + phase) / r["teeth"] - math.radians(3.3))
            pts.append((radius * math.cos(a), radius * math.sin(a)))
    return rounded_polygon(pts, r["fillet"])


def pawl_profile(b):
    d = direction(b)
    pts = [(8, -4.9), (10.2, -5), (12, -1.1), (14.35, -.7), (14.35, .7), (13.15, 1.1), (9.4, -.5), (8, -1.3)]
    outline = rounded_polygon([(u, v * d) for u, v in pts], .25)
    outline += bd.Pos(9.2, -3 * d) * bd.Circle(2.5)
    r = config()["ratchet"]
    # A heel outside the circular pivot lug gives the carrier a real contact
    # surface. A stop aimed only at the round lug cannot limit its rotation.
    u, v = r["heel_tab_u"], -r["heel_tab_v_abs"] * d
    w, h = r["heel_tab_width"], r["heel_tab_height"]
    outline += rounded_polygon([(u - w / 2, v - h / 2), (u + w / 2, v - h / 2),
                                (u + w / 2, v + h / 2), (u - w / 2, v + h / 2)], .2)
    outline -= bd.Pos(9.2, -3 * d) * bd.Circle(1.1)
    return outline


def engagement_stop_profile(b):
    r = config()["ratchet"]; d = direction(b)
    face = bd.Pos(r["heel_stop_u"], -r["heel_stop_v_abs"] * d) * bd.Rectangle(r["heel_stop_width"], r["heel_stop_height"])
    # The circular lug always has radial clearance; only the new heel contacts.
    face -= bd.Pos(9.2, -3 * d) * bd.Circle(r["pivot_relief_d"] / 2)
    return face


@lru_cache(maxsize=2)
def clutch_parts(b):
    p = config(); d = direction(b); n = 40 if b == "M" else 60
    output = gear(n, p["module"], 6, 0, p["backlash"])
    output -= bd.extrude(ratchet_profile(b), amount=4, both=True)
    root = p["module"] * n / 2 - 1.25 * p["module"]
    # Separate, bolt-clamped backplate eliminates a 29-mm cavity roof in FDM.
    backplate = bd.Pos(0, 0, -4) * ring(root - .2, 6.25, 2)
    backplate += bd.Pos(0, 0, -6) * ring(9.5, 6.25, 6)
    output -= bd.Compound(children=circle_holes(18.5, 1.1, 3, 22, 30))
    backplate -= bd.Compound(children=circle_holes(18.5, 1.1, 3, 22, 30))
    carrier = bd.Pos(0, 0, -1.3) * ring(12.6, 4.1, 2.4)
    carrier += bd.Pos(0, 0, 2.2) * ring(6.8, 4.1, 9.4)
    carrier += bd.Pos(0, 0, 1.4) * bd.extrude(engagement_stop_profile(b), amount=1.9, both=True)
    carrier -= bd.Pos(9.2, -3 * d, -1) * bd.Cylinder(1.0, 8)
    carrier -= bd.Pos(0, 0, 4.4) * bd.Rot(90, 0, 0) * bd.Cylinder(1.25, 20)
    pawn = bd.Pos(0, 0, 1.9) * bd.extrude(pawl_profile(b), amount=1.4, both=True)
    cover = bd.Pos(0, 0, 7.4) * ring(21.2, 8.4, 2)
    cover -= bd.Compound(children=circle_holes(18.5, 1.1, 3, 22, 30))
    return {"output": output, "backplate": backplate, "carrier": carrier, "pawl": pawn, "cover": cover,
            "bushing": bd.Pos(0, 0, -6) * ring(6.1, 4.25, 5.8)}


def clutch(b):
    p = config(); x = sign(b) * p["gear_x"]; y = p["input_y"]; z = p["axis_z"]
    pieces = []
    for role, shape in clutch_parts(b).items():
        pieces.append(named(place_axial(shape, x, y, z), "C" + b + "_" + role, "POM" if role == "bushing" else b))
    for k in range(3):
        a = math.radians(30 + k * 120)
        shape = bd.Pos(18.5 * math.cos(a), 18.5 * math.sin(a), 4.7) * ring(2.7, 1.1, 3.4)
        pieces.append(named(place_axial(shape, x, y, z), f"C{b}_post_{k}", b))
    pin = bd.Pos(9.2, -3 * direction(b), 1.2) * bd.Cylinder(1, 5)
    pieces.append(named(place_axial(pin, x, y, z), "C" + b + "_pin_ENVELOPE", "steel"))
    return group("Clutch_" + b, pieces)


def flange(b):
    f = config()["flap"]
    if b == "H":
        part = ring(flange_r(b), 4.2, f["flange_t"])
        part -= bd.Compound(children=circle_holes(pivot_r(b), f["bearing_bore_d"] / 2, count(b), 8))
        part -= bd.Compound(children=circle_holes(10, 1.65, 3, 8, 30))
        return part
    part = ring(f["flange_r"], 32.4, f["flange_t"])
    part += ring(16, 4.2, f["flange_t"])
    for a in range(0, 360, 45):
        part += bd.Rot(0, 0, a) * bd.Pos(24, 0, 0) * bd.Box(20, 3.2, f["flange_t"])
    part -= bd.Compound(children=circle_holes(f["pivot_r"], f["bearing_bore_d"] / 2, count(b), 8))
    part -= bd.Compound(children=circle_holes(12.5, 1.65, 3, 8, 30))
    return part


def core(b="M"):
    part = ring(8 if b == "H" else 10, 4.1, 34.8)
    for z in (-15.6, 15.6):
        part += bd.Pos(0, 0, z) * ring(13 if b == "H" else 16, 4.1, 3.6)
    part -= bd.Compound(children=circle_holes(10 if b == "H" else 12.5, 1.65, 3, 40, 30))
    part -= bd.Rot(90, 0, 0) * bd.Cylinder(1.25, 25)
    return part


def digit_boxes(value, upper=True, depth=.3):
    # Own vector alphabet from R1, resized. No external typeface or author text.
    segments = {"a": (0, 21, 13, 2.2), "g": (0, 0, 13, 2.2), "d": (0, -21, 13, 2.2),
                "f": (-7, 10.5, 2.2, 17), "b": (7, 10.5, 2.2, 17), "e": (-7, -10.5, 2.2, 17), "c": (7, -10.5, 2.2, 17)}
    f = config()["flap"]; s = 2 / 3; pieces = []
    for i, digit in enumerate((value // 10, value % 10)):
        off = -10.5 if i == 0 else 10.5
        for name in DIGITS[digit]:
            sx, sz, w, h = segments[name]; lo, hi = sz - h / 2, sz + h / 2
            lo, hi = (max(.22, lo), hi) if upper else (lo, min(-.22, hi))
            if hi <= lo:
                continue
            z = ((lo + hi) / 2) * s * (1 if upper else -1)
            y = f["panel_center_y"] + (f["thickness"] / 2 - depth / 2) * (1 if upper else -1)
            h_native = (hi - lo) * s
            if name == "g":
                z, h_native = 1.6, .8  # Clear the exposed solid spine at the split.
            pieces.append(bd.Pos(-(off + sx) * s, y, z) * bd.Box(w * s, depth, h_native))
    return group("glyph", pieces)


@lru_cache(maxsize=1)
def flap_blank():
    f = config()["flap"]
    plate = bd.Pos(0, f["panel_center_y"], f["length"] / 2) * bd.Box(f["width"], f["thickness"], f["length"])
    pin = cylinder_x(f["trunnion_d"] / 2, f["trunnion_length"])
    pin &= bd.Pos(0, (f["pin_flat_y"] + f["pin_front_flat_y"]) / 2, 0) * bd.Box(f["trunnion_length"] + 2, f["pin_front_flat_y"] - f["pin_flat_y"], 4)
    return plate + pin


def flap(k, b, paint=False):
    # Six 0.2-mm layers make the flexible functional sheet; graphics are a
    # post-print finish. Cutting a groove here would violate the 1.2-mm web.
    panel = flap_blank()
    if not paint:
        return panel
    colored = []
    for upper, val in ((True, k), (False, (k + 1) % count(b))):
        # A 0.05-mm paint film is a finish, deliberately absent from print STL.
        ink = digit_boxes(val, upper, .05)
        ink = bd.Pos(0, .05 if upper else -.05, 0) * ink
        colored.append(named(ink, f"F{b}_{k:02}_paint_{int(upper)}", "ink"))
    return group(f"F{b}_{k:02}", [named(panel, f"F{b}_{k:02}_panel", "flap"), *colored])


def flap_pose(k, b):
    p = config(); f = p["flap"]; angle = 360 * k / count(b); a = math.radians(angle)
    return bd.Pos(sign(b) * p["drum_x"], axis_y(b) + pivot_r(b) * math.cos(a), p["axis_z"] + pivot_r(b) * math.sin(a)) * bd.Rot(angle - 90 + f["initial_fan_tilt_deg"], 0, 0)


def drum(b):
    p = config(); x = sign(b) * p["drum_x"]; z = p["axis_z"]; f = p["flap"]
    yy = axis_y(b)
    parts = [named(place_axial(core(b), x, yy, z), "D" + b + "_core", b)]
    for s in (-1, 1):
        parts.append(named(place_axial(flange(b), x + s * f["flange_offset"], yy, z), f"D{b}_flange_{s}", b))
    # The 0.8 mm centre gap prevents the two outputs sharing a rigid shaft.
    parts.append(named(cylinder_x(4, 83.1, sign(b) * 41.95, yy, z), "D" + b + "_shaft_ENVELOPE", "steel"))
    parts += [flap_pose(k, b) * flap(k, b, paint=True) for k in range(count(b))]
    return group("Drum_" + b, parts)


def detent_points(b):
    d = config()["detent"]; n = count(b)
    return [((d["radius"] - d["depth"] * (1 + math.cos(n * a)) / 2) * math.cos(a),
             (d["radius"] - d["depth"] * (1 + math.cos(n * a)) / 2) * math.sin(a))
            for a in (2 * math.pi * j / (n * 16) for j in range(n * 16))]


def detent_profile(b):
    p = bd.Polygon(*detent_points(b), align=None)
    extrema = [v for v in p.vertices() if min(abs(math.hypot(v.X, v.Y) - r) for r in (30, 29.1)) < 1e-6]
    return bd.fillet(extrema, .3)


@lru_cache(maxsize=2)
def roller_radius(b):
    points = detent_points(b)
    def distance(c):
        result = 1e9
        for (ax, ay), (bx, by) in zip(points, points[1:] + points[:1]):
            dx, dy = bx - ax, by - ay
            t = max(0, min(1, ((c - ax) * dx - ay * dy) / (dx * dx + dy * dy)))
            result = min(result, math.hypot(c - ax - t * dx, ay + t * dy))
        return result
    lo, hi = 31.1, 32.1
    for _ in range(48):
        mid = (lo + hi) / 2
        if distance(mid) < 2.02:
            lo = mid
        else:
            hi = mid
    return hi


def detent_disc(b):
    part = bd.extrude(detent_profile(b), amount=1.5, both=True)
    part -= bd.Cylinder(4.1, 10)
    part -= bd.Compound(children=circle_holes(20, 5.5, 6, 10))
    part += bd.Pos(0, 0, 2.7) * ring(9, 4.1, 2.4)
    part -= bd.Pos(0, 0, 2.7) * bd.Rot(90, 0, 0) * bd.Cylinder(1.25, 24)
    return part


def detent(b):
    p = config(); s = sign(b); x = s * p["detent_x"]; z = p["axis_z"]; rz = z - roller_radius(b); pz = rz - 3
    arm_x = s * (p["detent_x"] + 4)
    arm = bd.Pos(arm_x, -9, (pz + rz) / 2) * bd.Box(2.8, 23, 8)
    arm -= cylinder_x(1.15, 8, arm_x, -18, pz)
    arm -= cylinder_x(1.15, 8, arm_x, 0, rz)
    bracket = bd.Pos(x, -18, (pz + 4.8) / 2) * bd.Box(4, 10, pz - 4.8)
    bracket += cylinder_x(4, 4, x, -18, pz)
    bracket += bd.Pos(s * 52.5, -5, 7.2) * bd.Box(14, 28, 4.8)
    bracket += bd.Pos(s * 60, -8, 9) * bd.Box(11, 30, 3)
    bracket -= cylinder_x(1.15, 12, x, -18, pz)
    for y in (-15, 5):
        bracket -= bd.Pos(s * 52.5, y, 8) * bd.Cylinder(1.7, 12)
    bottom = (pz + rz) / 2 - 4; sx = s * 61.1
    wire_r = .22 if b == "H" else .2
    spring = bd.Pos(sx, 2, 10.5 + wire_r) * wire_spring(2.5, wire_r, 6, (bottom - 10.5 - 2 * wire_r) / 6)
    parts = [named(place_axial(detent_disc(b), x, 0, z), "DE" + b + "_cam", b),
             named(arm, "DE" + b + "_arm", "POM"), named(bracket, "DE" + b + "_bracket", "dark"),
             named(cylinder_x(2, 4, x, 0, rz) - cylinder_x(1.1, 6, x, 0, rz), "DE" + b + "_roller_ENVELOPE", "POM"),
             named(cylinder_x(1, 6.5, s * 60.5, 0, rz), "DE" + b + "_roller_pin_ENVELOPE", "steel"),
             named(cylinder_x(1, 8, s * 60, -18, pz), "DE" + b + "_pivot_pin_ENVELOPE", "steel"),
             named(spring, "DE" + b + "_spring_ENVELOPE", "steel")]
    knob = ring(13, 4.1, 5.6)
    knob -= bd.Rot(90, 0, 0) * bd.Cylinder(1.25, 30)
    parts.append(named(place_axial(knob, s * 76.4, 0, z), "K" + b + "_service_knob", b))
    return bd.Pos(0, axis_y(b), 0) * group("Detent_" + b, parts)


def retainers():
    p = config(); r = p["retainer"]; parts = []
    for b in ("M", "H"):
        cx = sign(b) * p["drum_x"]
        parts.append(named(cylinder_x(.5, 40, cx, r["y"], r["z"]), "R" + b + "_steel_wire_ENVELOPE", "steel"))
    return group("Retainers", parts)


def sensors():
    p = config(); parts = []
    for b in ("M", "H"):
        s = sign(b); z = p["axis_z"]
        cap = bd.Cylinder(7, 6) - bd.Pos(0, 0, -2) * bd.Cylinder(4.1, 4)
        cap -= bd.Pos(0, 0, 2.9) * bd.Cylinder(3.1, 2.2)
        if s < 0:
            cap = bd.Rot(180, 0, 0) * cap
        holder = bd.Pos(s * 88, 0, (z + 4.8) / 2) * bd.Box(2.4, 22, z - 4.8)
        holder += bd.Pos(s * 85, 0, 7.2) * bd.Box(12, 30, 4.8)
        holder -= cylinder_x(5, 6, s * 88, 0, z)
        for yy in (-10, 10):
            holder -= bd.Pos(s * 85, yy, 8) * bd.Cylinder(1.7, 12)
        parts += [bd.Pos(0, axis_y(b), 0) * item for item in [named(holder, "S" + b + "_encoder_holder", "dark"),
                  named(place_axial(cap, s * 83.5, 0, z), "S" + b + "_magnet_cap", "POM"),
                  named(cylinder_x(3, 2, s * 86.3, 0, z), "S" + b + "_magnet_ENVELOPE", "steel"),
                  named(bd.Pos(s * 90, 0, z) * bd.Box(1.6, 20, 20), "S" + b + "_PCB_ENVELOPE", "pcb")]]
    return group("Output_feedback", parts)


def drive():
    p = config(); z = p["axis_z"]; y = p["input_y"]; parts = []
    parts.append(named(cylinder_x(4, 150, 0, y, z), "I_common_shaft_ENVELOPE", "steel"))
    for b in ("M", "H"):
        phase = 0 if b == "M" else hour_train()["output_phase"]
        parts.append(named(place_axial(gear(40, 1.2, 6, 8.2, .22), sign(b) * 50, axis_y(b), z, phase), "T" + b + "_output_gear", b))
    parts.append(named(place_axial(gear(20, 1.2, 6, 5.2, .22), -50, -36, z, 9), "T_idler", "M"))
    pedestal = bd.Pos(-59, -36, (z + 4.8) / 2) * bd.Box(6.4, 12, z - 4.8)
    pedestal += bd.Pos(-59, -36, 7.2) * bd.Box(6.4, 34, 4.8)
    pedestal -= cylinder_x(2.6, 10, -59, -36, z)
    for yy in (-46, -26.5):
        pedestal -= bd.Pos(-59, yy, 8) * bd.Cylinder(1.7, 12)
    pedestal -= bd.Pos(-59, 26.7, 40) * bd.Box(30, 100, 100)  # All Y >= -23.3; 0.3-mm detent clearance.
    parts += [named(pedestal, "T_idler_pedestal", "dark"), named(cylinder_x(2.5, 20, -54, -36, z), "T_idler_pin_ENVELOPE", "steel")]
    ht = hour_train(); hy = sum(c[0] for c in ht["centres"]) / 2; hz = ht["centres"][0][1]
    support = bd.Pos(62.8, hy, 7.2) * bd.Box(6, 58, 4.8)
    support += bd.Pos(62.8, hy, hz) * bd.Box(6, 24, 12)
    for i, ((yy, zz), ph) in enumerate(zip(ht["centres"], ht["phases"])):
        parts.append(named(place_axial(gear(20, 1.2, 6, 5.2, .22), 50, yy, zz, ph), f"TH_idler_{i}", "H"))
        support += bd.Pos(62.8, yy, (zz + 4.8) / 2) * bd.Box(6, 12, zz - 4.8)
        support -= cylinder_x(2.6, 10, 62.8, yy, zz)
        parts.append(named(cylinder_x(2.5, 20, 57, yy, zz), f"TH_idler_pin_{i}_ENVELOPE", "steel"))
    support -= bd.Pos(62.8, 48.3, 60) * bd.Box(30, 100, 120)  # All Y >= -1.7; no stationary foot overlap.
    for yy in (ht["centres"][0][0] - 11, -14):
        support -= bd.Pos(62.8, yy, 8) * bd.Cylinder(1.7, 12)
    parts.append(named(support, "TH_idler_bridge", "dark"))
    # Real belt envelope, not an ideal output transmission constraint.
    belt = p["belt"]; motor_y = y - math.sqrt(belt["center_distance"] ** 2 - (z - belt["motor_z"]) ** 2)
    pr = belt["pulley_teeth"] * belt["pitch"] / (2 * math.pi)
    mz = belt["motor_z"]; centre = belt["center_distance"]
    for yy, zz, name in ((y, z, "I_input_pulley_ENVELOPE"), (motor_y, mz, "E_motor_pulley_ENVELOPE")):
        wheel = ring(pr + 1, 4.1 if name.startswith("I") else 2.6, 8)
        parts.append(named(place_axial(wheel, 5, yy, zz), name, "steel"))
    # Two tangent spans plus semicircles represented by a native planar slot ring.
    band = bd.extrude(bd.SlotCenterToCenter(centre, 2 * (pr + .7)), amount=3, both=True)
    band -= bd.extrude(bd.SlotCenterToCenter(centre, 2 * (pr - .7)), amount=4, both=True)
    # Slot long axis local X; align in world YZ with its two centres.
    theta = math.degrees(math.atan2(motor_y - y, -(mz - z)))
    # RY maps local X to -Z, local Y to +Y. theta maps span to target delta.
    band = place_axial(bd.Rot(0, 0, theta) * band, 5, (motor_y + y) / 2, (mz + z) / 2)
    parts.append(named(band, "E_belt_144mm_ENVELOPE", "belt"))
    parts.append(named(cylinder_x(14, 20, 22, motor_y, mz), "E_gearmotor_ENVELOPE_UNSELECTED", "steel"))
    parts.append(named(cylinder_x(2.5, 10, 7, motor_y, mz), "E_motor_shaft_ENVELOPE", "steel"))
    collar = cylinder_x(17.3, 12, 22, motor_y, mz) - cylinder_x(14.1, 14, 22, motor_y, mz)
    mount = collar & (bd.Pos(22, motor_y, mz - 25.1) * bd.Box(40, 50, 50))
    clamp = collar & (bd.Pos(22, motor_y, mz + 25.1) * bd.Box(40, 50, 50))
    mount += bd.Pos(22, motor_y, 8) * bd.Box(26, 42, 6.4)
    for s in (-1, 1):
        yy = motor_y + s * 18
        mount += bd.Pos(22, yy, mz - 2.1) * bd.Box(12, 7.6, 4)
        clamp += bd.Pos(22, yy, mz + 2.1) * bd.Box(12, 7.6, 4)
        mount -= bd.Pos(22, yy, mz) * bd.Cylinder(1.7, 16)
        mount -= bd.Pos(22, yy, mz - 4.1) * bd.extrude(bd.RegularPolygon(3.3, 6), amount=2.4)
        clamp -= bd.Pos(22, yy, mz) * bd.Cylinder(1.7, 16)
    for x in (12, 28):
        mount -= bd.Pos(x, -96, 8) * bd.extrude(bd.SlotOverall(8, 3.4), amount=6, both=True)
    parts.append(named(mount, "E_slotted_motor_saddle", "dark"))
    parts.append(named(clamp, "E_motor_top_clamp", "dark"))
    for b in ("M", "H"):
        for yy in (axis_y(b), y):
            # Existing R1 608 nominal envelope; purchasing fits remain pending.
            bearing = ring(11, 4, 7)
            parts.append(named(place_axial(bearing, sign(b) * p["frame_x"], yy, z), f"B{b}_{int(yy)}_608_ENVELOPE", "steel"))
        parts.append(named(place_axial(ring(6, 4.2, 2.6), sign(b) * 1.7, axis_y(b), z), "B" + b + "_center_bush", "POM"))
    return group("Input_and_transmission", parts)


def mechanism():
    return group("FC_R2_mechanism_INITIAL_POSE", [base(), side_frame("M"), side_frame("H"), center_frame(),
            drive(), clutch("M"), clutch("H"), drum("M"), drum("H"), detent("M"), detent("H"), retainers(), sensors()])


def assembly():
    return group("FC_R2_Desktop_PROTOTYPE", [mechanism(), hood(), panel(True), panel(False), bezel(), *colon_inlays()])


def coupons():
    parts = [named(bd.Pos(-32, 0, 0) * flap(8, "M"), "CP_numbered_flap", "flap")]
    # Exact pin and bore ladders: four material-specific diameter clearances.
    block = bd.Pos(20, 0, 1.5) * bd.Box(26, 18, 3)
    for i, diameter in enumerate((2.4, 2.5, 2.6, 2.7)):
        block -= bd.Pos(11 + i * 6, 0, 1.5) * bd.Cylinder(diameter / 2, 6)
    parts.append(named(block, "CP_trunnion_bore_ladder", "M"))
    return group("FC_R2_fit_coupons", parts)
