"""Original parametric geometry for FC-R1; millimetres, X axles, +Y front.

No imported author meshes, inferred original dimensions, fonts, or vendor CAD.
Standard motor/bearing envelopes are separately identified and not printable parts.
The radial flap pose is a CAD inspection pose, not a gravity solution.
"""
from __future__ import annotations

from functools import lru_cache
import math
from cadgen import build123d as bd, srgb
from settings import values

COLORS = {"frame": "#374653", "minute": "#1E9A9C", "hour": "#EBA44A",
          "flap": "#14202C", "ink": "#F3EFDF", "steel": "#9AA8B4",
          "spring": "#C2A66D", "bushing": "#DFD6BF", "pcb": "#266549"}


def branch_sign(branch):
    # Seen from +Y, screen-right is -X: hours at +X, minutes at -X.
    return 1 if branch=="H" else -1


def named(shape, label, color="frame"):
    shape.label = label
    shape.color = srgb(COLORS.get(color, color))
    return shape


def group(label, parts):
    return bd.Compound(children=list(parts), label=label)


def place_axial(shape, x=0, y=0, z=0, phase=0):
    return bd.Pos(x, y, z) * bd.Rot(0, 90, 0) * bd.Rot(0, 0, phase) * shape


def cylinder_x(radius, length, x=0, y=0, z=0):
    return place_axial(bd.Cylinder(radius, length), x, y, z)


def ring(ro, ri, height):
    return bd.Cylinder(ro, height) - bd.Cylinder(ri, height + 2)


def circle_holes(radius, hole_radius, n, height, phase=0):
    return [bd.Pos(radius * math.cos(a), radius * math.sin(a), 0) * bd.Cylinder(hole_radius, height)
            for a in (math.radians(phase + 360 * k / n) for k in range(n))]


def rounded_polygon(points, radius):
    sketch = bd.Polygon(*points, align=None)
    return bd.fillet(sketch.vertices(), radius) if radius else sketch


def gear_profile(teeth, module, backlash, pressure_deg=20):
    """Sampled involute, finite tip land, radial dedendum and rounded root.

    Both flanks use 14 radial samples, computed from the involute equation.
    Root fillets are native circular fillets. No overlapping-cylinder teeth.
    """
    pitch = module * teeth / 2
    base = pitch * math.cos(math.radians(pressure_deg))
    root = pitch - 1.25 * module
    tip = pitch + module
    inv_alpha = math.tan(math.radians(pressure_deg)) - math.radians(pressure_deg)
    half = math.pi / (2 * teeth) - backlash / (4 * pitch)

    def half_at(r):
        phi = math.acos(min(1.0, base / r))
        return half + inv_alpha - (math.tan(phi) - phi)

    low = max(base, root)
    edges = []
    def polar(r, a):
        return (r * math.cos(a), r * math.sin(a), 0)
    def arc(r, a, b):
        return bd.Edge.make_three_point_arc(polar(r,a), polar(r,(a+b)/2), polar(r,b))
    for k in range(teeth):
        center = 2 * math.pi * k / teeth
        flank = half_at(low)
        edges.append(arc(root,center-math.pi/teeth,center-flank))
        left, right = [], []
        for j in range(24):
            r = root + (tip-root)*j/23
            half_angle=half_at(max(base,r))
            left.append(polar(r,center-half_angle))
            right.append(polar(r,center+half_angle))
        edges.append(bd.Edge.make_spline(left))
        edges.append(arc(tip,center-half_at(tip),center+half_at(tip)))
        edges.append(bd.Edge.make_spline(list(reversed(right))))
        edges.append(arc(root,center+flank,center+math.pi/teeth))
    sketch = bd.Face(bd.Wire(edges))
    roots = [v for v in sketch.vertices()
             if abs(math.hypot(v.X,v.Y)-root)<1e-5
             and abs((math.atan2(v.Y,v.X)*teeth/(2*math.pi)+.5)%1-.5)<.49]
    return bd.fillet(roots, module * 0.25)


@lru_cache(maxsize=16)
def gear(teeth, module, width, bore, backlash):
    shape = bd.extrude(gear_profile(teeth, module, backlash), amount=width / 2, both=True)
    return shape - bd.Cylinder(bore / 2, width + 2) if bore > 0 else shape


def ratchet_cavity(teeth=36, direction=1):
    p = values()
    low, high = p["ratchet_tip_radius"], p["ratchet_root_radius"]
    points = []
    for k in range(teeth):
        for phase, r in ((0, high), (.20, high), (.32, low), (.46, low), (.98, high)):
            a = direction * 2 * math.pi * (k + phase) / teeth
            points.append((r * math.cos(a), r * math.sin(a)))
    return rounded_polygon(points, p["ratchet_fillet"])


def pawl(direction=1):
    p = values()
    outline = [(12.6, -7.3), (15.7, -8), (22.9, -.35), (22.9, .35),
               (21.8, .75), (14, -2.8), (12.6, -4)]
    profile = rounded_polygon([(x, y * direction) for x, y in outline], .22)
    part = bd.extrude(profile, amount=p["pawl_width"] / 2, both=True)
    part -= bd.Pos(15, -5.5 * direction, 0) * bd.Cylinder(1.15, p["pawl_width"] + 2)
    return part


def wire_spring(radius=1.8, wire=.32, turns=3, pitch=.8):
    path = bd.Helix(pitch=pitch, height=turns * pitch, radius=radius)
    start = path @ 0
    section = bd.Plane(origin=start, z_dir=path % 0) * bd.Circle(wire)
    return bd.sweep(section, path=path)


def clutch_components(direction=1, teeth=36, gear_teeth=40):
    p = values()
    module, width = p["gear_module"], p["gear_width"]
    output = gear(gear_teeth, module, width, 0, p["gear_backlash"])
    cavity = bd.extrude(ratchet_cavity(teeth, direction), amount=width / 2 + 1, both=True)
    output = output - cavity
    root = module * gear_teeth / 2 - 1.25 * module
    back = bd.Pos(0, 0, -4) * ring(root - .2, 6.25, 2)
    neck = bd.Pos(0, 0, -6) * ring(9.5, 6.25, 6)
    output = output + back + neck
    output -= bd.Compound(children=circle_holes(28, 1.65, 3, 18, 30))
    carrier = bd.Pos(0, 0, -.9) * ring(18.5, 4.1, 2)
    carrier += bd.Pos(0, 0, 2) * ring(7.8, 4.1, 9.8)
    carrier -= bd.Pos(15, -5.5 * direction, 0) * bd.Cylinder(1.0, 7)
    # Physical heel stop, not a software one-way constraint.
    stop = bd.Pos(17.3, -8.6 * direction, 1.5) * bd.Box(2.0, 2.0, 2.8)
    carrier += stop
    clamp_tool = bd.Pos(0, 0, 4.4) * bd.Rot(90, 0, 0) * bd.Cylinder(1.25, 20)
    carrier -= clamp_tool
    moving_pawl = bd.Pos(0, 0, 1.6) * pawl(direction)
    pin = bd.Pos(15, -5.5 * direction, .6) * bd.Cylinder(1, 5.0)
    spring = bd.Pos(15, -5.5 * direction, 3.1) * wire_spring()
    # Spring legs have real geometry; load/stiffness remains a measured input.
    leg_a = bd.Pos(16.8, -7.5 * direction, 3.1) * bd.Rot(90, 0, 0) * bd.Cylinder(.32, 4)
    leg_b = bd.Pos(13.2, -3.9 * direction, 5.5) * bd.Rot(90, 0, 0) * bd.Cylinder(.32, 3.2)
    bush = bd.Pos(0, 0, -6) * ring(6.1, 4.25, 5.8)
    cover = bd.Pos(0, 0, 6.9) * ring(31.2, 8.4, 1.5)
    cover -= bd.Compound(children=circle_holes(28, 1.65, 3, 20, 30))
    # The posts support the cover independently of the carrier/pawl.
    posts = [bd.Pos(28 * math.cos(a), 28 * math.sin(a), 4.575) * ring(2.6, 1.65, 3.15)
             for a in (math.radians(30 + k*120) for k in range(3))]
    return {"output": output, "carrier": carrier, "pawl": moving_pawl,
            "pin": pin, "spring": group("spring_coil_and_legs", [spring, leg_a, leg_b]),
            "bushing": bush, "cover": cover, "posts": group("cover_posts", posts)}


def clutch_group(branch="M", teeth=None, exploded=False):
    p = values()
    direction = 1 if branch == "M" else -1
    gear_teeth = p["minute_driver_teeth"] if branch == "M" else p["hour_driver_teeth"]
    parts = clutch_components(direction, teeth or p["ratchet_teeth"], gear_teeth)
    result = []
    for i, (role, part) in enumerate(parts.items()):
        if exploded:
            part = bd.Pos(0, 0, i * 10) * part
        color = "steel" if role == "pin" else "spring" if role == "spring" else "bushing" if role == "bushing" else "minute" if branch == "M" else "hour"
        result.append(named(part, f"C{branch}_{role}", color))
    return group("ClutchMinute" if branch == "M" else "ClutchHour", result)


def bearing(label):
    # Deliberately simplified purchased 608ZZ envelope, not a print part.
    outer = named(ring(11, 8.3, 7), label + "_outer_race", "steel")
    inner = named(ring(6.2, 4, 7), label + "_inner_race", "steel")
    shield = named(ring(8.3, 6.2, 6.2), label + "_shield_envelope", "#687580")
    return group(label, [outer, inner, shield])


def bolt(label, length=12, diameter=3):
    shaft = bd.Pos(0, 0, -length / 2) * bd.Cylinder(diameter / 2, length)
    head = bd.Pos(0, 0, diameter / 2) * bd.Cylinder(diameter * .9, diameter)
    socket = bd.Pos(0, 0, diameter) * bd.extrude(bd.RegularPolygon(diameter * .4, 6), amount=-diameter * .65)
    return named(shaft + head - socket, label, "steel")


def foundation_holes():
    p=values()
    holes=[(x,y) for x in (-99,99) for y in (-128,20)]
    holes += [(-17,0),(17,0)]
    holes += [(x,y) for x in (-131,131) for y in (-8,8)]
    holes += [(-137,-126),(-137,-90)]
    holes += [(x,y) for x in (-(p["detent_plane_x"]-4),p["detent_plane_x"]-4) for y in (-28,-8)]
    holes += [(x,y) for x in (-12,12) for y in (83,95)]
    return holes


def seam_holes():
    return [(x,y) for x in (-16,16) for y in (-148,64)]+[(x,y) for x in (-45,45) for y in (-50,-18)]


def fasteners():
    parts=[]
    items=[(x,y,12,12,"foundation") for x,y in foundation_holes()]
    items += [(x,y,9,10,"seam") for x,y in seam_holes()]
    for index,(x,y,top,length,role) in enumerate(items):
        parts.append(bd.Pos(x,y,top)*bolt(f"B00_{role}_M3x{length}_{index:02}",length))
        nut=bd.extrude(bd.RegularPolygon(3.18,6),amount=2.4)
        nut-=bd.Pos(0,0,1.2)*bd.Cylinder(1.3,4)
        parts.append(named(bd.Pos(x,y,0)*nut,f"B01_foundation_M3_nut_{index:02}","steel"))
    return group("Fasteners",parts)


def frame():
    p = values()
    axis_z, rear = p["axis_height"], p["input_axis_y"]
    base = bd.Pos(-12, -34, 3) * bd.Box(312, 280, 6)
    for x, y in foundation_holes()+seam_holes():
        base -= bd.Pos(x, y, 3) * bd.Cylinder(1.7, 10)
        base -= bd.Pos(x,y,-.1)*bd.extrude(bd.RegularPolygon(3.3,6),amount=2.7)
    for x in (-154, 130):
        for y in (-160, 76):
            base -= bd.Pos(x, y, 3) * bd.Cylinder(2.2, 10)
    parts=[]
    # Four bolted tiles fit within a 180 x 180 mm print envelope.
    for x0,x1,side in ((-168,0,"L"),(0,144,"R")):
        for y0,y1,row in ((-174,-34,"rear"),(-34,106,"front")):
            region=bd.Pos((x0+x1)/2,(y0+y1)/2,3)*bd.Box(x1-x0,y1-y0,8)
            parts.append(named(base & region,f"A00_base_{side}_{row}"))
    for y in (-148,64):
        strap=bd.Pos(0,y,7.5)*bd.Box(48,14,3)
        for x in (-16,16):strap-=bd.Pos(x,y,7.5)*bd.Cylinder(1.7,8)
        parts.append(named(strap,f"A03_X_seam_strap_{'rear' if y<0 else 'front'}"))
    for x in (-45,45):
        strap=bd.Pos(x,-34,7.5)*bd.Box(14,48,3)
        for y in (-50,-18):strap-=bd.Pos(x,y,7.5)*bd.Cylinder(1.7,8)
        parts.append(named(strap,f"A03_Y_seam_strap_{'L' if x<0 else 'R'}"))
    for i,(x,y) in enumerate(((-154,-160),(-154,92),(130,-160),(130,92))):
        parts.append(named(bd.Pos(x,y,-1)*bd.Cylinder(7,2),f"A04_TPU_foot_{i}","bushing"))
    for sign, label in ((-1, "M"), (1, "H")):
        x = sign * p["frame_x"]
        wall = bd.Pos(x, rear / 2, 9) * bd.Box(18, 160, 6)
        for y in (0, rear):
            wall += bd.Pos(x, y, (axis_z + 12) / 2) * bd.Box(6, 27, axis_z - 12)
            wall += cylinder_x(16, 6, x, y, axis_z)
        wall += bd.Pos(x, rear / 2, axis_z) * bd.Box(6, abs(rear), 16)
        for y in (0, rear):
            wall -= cylinder_x(11.1, 10, x, y, axis_z)
        wall -= cylinder_x(2.5, 10, x, rear/2, axis_z)
        for y in (-128, 20):
            wall -= bd.Pos(x, y, 9) * bd.Cylinder(1.7, 10)
        parts.append(named(wall, f"A01_side_frame_{label}"))
    center = bd.Pos(0, 0, (axis_z + 6)/2) * bd.Box(22, 25, axis_z - 6)
    center += cylinder_x(16, 22, 0, 0, axis_z)
    for sign in (-1, 1):
        center -= cylinder_x(11.1, 7.1, sign * 7.5, 0, axis_z)
    center += bd.Pos(0, 0, 9) * bd.Box(42, 32, 6)
    for x in (-17,17):
        center -= bd.Pos(x, 0, 9) * bd.Cylinder(1.7, 10)
    parts.append(named(center, "A02_center_twin_bearing_pedestal"))
    for label, x, y in (("H_outer", 99, 0), ("M_outer", -99, 0),
                         ("H_inner", 7.5, 0), ("M_inner", -7.5, 0),
                         ("I_left", -99, rear), ("I_right", 99, rear)):
        parts.append(place_axial(bearing("H00_608_" + label), x, y, axis_z))
    return group("Frame", parts)


def input_drive():
    p = values()
    y, z = p["input_axis_y"], p["axis_height"]
    parts = [named(cylinder_x(4, 240, 0, y, z), "A10_common_input_shaft", "steel")]
    coupler = bd.Cylinder(9, 18)
    coupler -= bd.Pos(0, 0, -4.5) * bd.Cylinder(2.6, 10)
    coupler -= bd.Pos(0, 0, 4.5) * bd.Cylinder(4.1, 10)
    coupler -= bd.Pos(0, 0, -4) * bd.Rot(90, 0, 0) * bd.Cylinder(1.25, 22)
    coupler -= bd.Pos(0, 0, 4) * bd.Rot(90, 0, 0) * bd.Cylinder(1.25, 22)
    parts.append(named(place_axial(coupler, -124, y, z), "A11_5_to_8_coupler", "minute"))
    mount = bd.Pos(-132, y, 48) * bd.Box(3, 52, 84)
    mount -= cylinder_x(10, 8, -132, y, z)
    for dy in (-17.5, 17.5):
        slot = bd.Pos(-132, y + dy, z - 8) * bd.Rot(0, 90, 0) * bd.extrude(bd.SlotOverall(9, 4.2), amount=5, both=True)
        mount -= slot
    mount += bd.Pos(-137, y, 9) * bd.Box(16, 52, 6)
    for dy in (-18,18):
        mount-=bd.Pos(-137,y+dy,9)*bd.Cylinder(1.7,12)
    parts.append(named(mount, "A12_adjustable_motor_mount"))
    motor = named(cylinder_x(14, 20, -144, y, z - 8), "E00_28BYJ48_body_ENVELOPE", "steel")
    motor_shaft = named(cylinder_x(2.5, 10, -129, y, z), "E00_output_shaft_ENVELOPE", "steel")
    parts.extend((motor, motor_shaft))
    return group("InputDrive", parts)


def transmission(branch):
    p = values()
    sign=branch_sign(branch)
    x = p["gear_plane_x"] * sign
    teeth = p["minute_output_teeth"] if branch == "M" else p["hour_output_teeth"]
    phase = 0 if branch == "M" else 180 / teeth
    shape = gear(teeth, p["gear_module"], p["gear_width"], 8.2, p["gear_backlash"])
    hub = bd.Pos(0, 0, 4.5) * ring(9, 4.1, 3)
    shape += hub
    shape -= bd.Pos(0, 0, 4) * bd.Rot(90, 0, 0) * bd.Cylinder(1.25, 24)
    if sign<0:shape=bd.Rot(180,0,0)*shape
    parts = [named(place_axial(shape, x, 0, p["axis_height"], phase), f"A4{branch}_drum_gear", "minute" if branch == "M" else "hour")]
    if branch == "M":
        idler = gear(p["minute_idler_teeth"], p["gear_module"], p["gear_width"], 5.5, p["gear_backlash"])
        parts.append(named(place_axial(idler, x, p["input_axis_y"] / 2, p["axis_height"], 180 / p["minute_idler_teeth"]), "A40M_idler", "minute"))
        start=p["gear_plane_x"]-6
        parts.append(named(cylinder_x(2.5,p["frame_x"]-start,sign*(p["frame_x"]+start)/2,p["input_axis_y"]/2,p["axis_height"]),"H03_idler_fixed_pin","steel"))
        parts.append(named(place_axial(ring(4.5, 2.7, 6), x, p["input_axis_y"]/2, p["axis_height"]), "H04_idler_bushing", "bushing"))
    return group("TransmissionM" if branch == "M" else "TransmissionH", parts)


def drum_core():
    p = values()
    part = ring(14, 4.1, 50)
    for z in (-23, 23):
        part += bd.Pos(0, 0, z) * ring(23, 4.1, 4)
    part -= bd.Compound(children=circle_holes(18, 1.65, 3, 54, 30))
    part -= bd.Pos(0, 0, 0) * bd.Rot(90, 0, 0) * bd.Cylinder(1.25, 34)
    return part


def drum_flange(count):
    p = values()
    part = ring(p["flange_radius"], 4.2, 3)
    part -= bd.Compound(children=circle_holes(p["flap_pivot_radius"], p["flap_pin_bore"]/2, count, 6))
    part -= bd.Compound(children=circle_holes(18, 1.65, 3, 6, 30))
    part -= bd.Compound(children=circle_holes(32, 9, 6, 6))
    return part


@lru_cache(maxsize=2)
def flap_blank():
    p = values()
    plate = bd.Pos(0, 0, p["flap_length"]/2) * bd.Box(p["flap_width"], p["flap_thickness"], p["flap_length"])
    barrel = cylinder_x(p["flap_barrel_radius"], p["flap_width"])
    part = plate + barrel
    part -= cylinder_x(p["flap_pin_bore"]/2, p["flap_width"] + 2)
    return part


DIGITS = {0:"abcedf",1:"bc",2:"abged",3:"abgcd",4:"fgbc",5:"afgcd",6:"afgecd",7:"abc",8:"abcdefg",9:"abfgcd"}


def ink_half(value, upper=True):
    """Own seven-segment vector alphabet, split at the hinge, no external font.

    Leaf k: face A = upper(k), face B = lower(k+1). B is inverted in Z so
    rotation of the physical leaf by 180 degrees exposes the correct lower half.
    """
    p = values()
    segments = {"a": (0, 21, 13, 2.2), "g": (0, 0, 13, 2.2), "d":(0,-21,13,2.2),
                "f":(-7,10.5,2.2,17), "b":(7,10.5,2.2,17),
                "e":(-7,-10.5,2.2,17), "c":(7,-10.5,2.2,17)}
    pieces = []
    for index, digit in enumerate((value//10, value%10)):
        offset = -10.5 if index == 0 else 10.5
        for name in DIGITS[digit]:
            sx, sz, width, height = segments[name]
            low, high = sz-height/2, sz+height/2
            lo, hi = (max(0.22,low), high) if upper else (low, min(-.22,high))
            if hi <= lo:
                continue
            if upper:
                z, y = (lo+hi)/2, p["flap_thickness"]/2 + .12
            else:
                z, y = -(lo+hi)/2, -p["flap_thickness"]/2 - .12
            pieces.append(bd.Pos(-(offset+sx), y, z) * bd.Box(width, .24, hi-lo))
    return bd.Compound(children=pieces)


def drum(branch):
    p = values()
    count = p["minute_flaps"] if branch == "M" else p["hour_flaps"]
    sign=branch_sign(branch)
    x = p["drum_center_x"] * sign
    z, r = p["axis_height"], p["flap_pivot_radius"]
    color = "minute" if branch == "M" else "hour"
    parts = [named(place_axial(drum_core(), x, 0, z), f"D{branch}_core", color)]
    for flange_side in (-1, 1):
        parts.append(named(place_axial(drum_flange(count), x+flange_side*26.5, 0, z), f"D{branch}_flange_{'L' if flange_side<0 else 'R'}", color))
    shaft_x = 60 * sign
    parts.append(named(cylinder_x(4, 112, shaft_x, 0, z), f"D{branch}_independent_output_shaft", "steel"))
    for k in range(count):
        # With q>0 about +X, the next numbered leaf must approach a fixed
        # display/release azimuth from the negative-angle side.
        angle = -360 * k / count
        phi = math.radians(angle)
        pose = bd.Pos(x, r*math.cos(phi), z+r*math.sin(phi)) * bd.Rot(angle-90, 0, 0)
        leaf = [named(pose * flap_blank(), f"F{branch}_{k:02}_panel", "flap"),
                named(pose * ink_half(k, True), f"F{branch}_{k:02}_upper_{k:02}", "ink"),
                named(pose * ink_half((k+1)%count, False), f"F{branch}_{k:02}_lower_{(k+1)%count:02}", "ink")]
        parts.append(group(f"F{branch}_{k:02}", leaf))
        parts.append(named(cylinder_x(1, 58, x, r*math.cos(phi), z+r*math.sin(phi)), f"P{branch}_{k:02}_flap_pin", "steel"))
    return group("DrumM" if branch == "M" else "DrumH24", parts)


def detent_outline_points(count):
    p = values()
    pts = []
    for j in range(count*16):
        a = 2*math.pi*j/(count*16)
        r = p["detent_radius"] - p["detent_depth"]*(1+math.cos(count*a))/2
        pts.append((r*math.cos(a),r*math.sin(a)))
    return pts


def detent_roller_center_radius(count):
    """Geometric inspection mate, not a preload or dynamics solution.

    The roller cannot be placed merely at valley_radius + roller_radius:
    its sides can intersect adjacent groove flanks. Solve distance to all
    polygon segments, then leave 0.02 mm for inspection and the root rounds.
    """
    p=values()
    points=detent_outline_points(count)
    segments=list(zip(points,points[1:]+points[:1]))
    def minimum_distance(c):
        minimum=float("inf")
        for (ax,ay),(bx,by) in segments:
            dx,dy=bx-ax,by-ay
            t=max(0,min(1,((c-ax)*dx-ay*dy)/(dx*dx+dy*dy)))
            minimum=min(minimum,math.hypot(c-ax-t*dx,ay+t*dy))
        return minimum
    lo=p["detent_radius"]-p["detent_depth"]+2
    hi=p["detent_radius"]+2.1
    for _ in range(48):
        mid=(lo+hi)/2
        if minimum_distance(mid)<2.02:lo=mid
        else:hi=mid
    return hi


def detent_disc(count):
    p=values()
    pts=detent_outline_points(count)
    profile = bd.Polygon(*pts, align=None)
    extrema=[v for v in profile.vertices() if any(abs(math.hypot(v.X,v.Y)-r)<1e-6 for r in (p["detent_radius"],p["detent_radius"]-p["detent_depth"]))]
    profile=bd.fillet(extrema,.4)
    part = bd.extrude(profile, amount=1.5, both=True)
    part -= bd.Cylinder(4.1, 8)
    part -= bd.Compound(children=circle_holes(26, 8, 6, 8))
    hub = bd.Pos(0,0,2.7)*ring(9,4.1,2.4)
    part += hub
    part -= bd.Pos(0,0,2.7)*bd.Rot(90,0,0)*bd.Cylinder(1.25,24)
    return part


def knob():
    part = ring(17,4.1,7)
    part -= bd.Compound(children=circle_holes(17,2,18,11))
    part -= bd.Rot(90,0,0)*bd.Cylinder(1.25,40)
    return part


def detent(branch):
    p = values()
    sign = branch_sign(branch)
    x, z = sign*p["detent_plane_x"], p["axis_height"]
    count = p["minute_flaps"] if branch=="M" else p["hour_flaps"]
    roller_z = z-detent_roller_center_radius(count)
    pivot_y, pivot_z = -18, roller_z-3
    disc=detent_disc(count)
    if sign>0:disc=bd.Rot(180,0,0)*disc
    parts = [named(place_axial(disc,x,0,z),f"DE{branch}_scallop_disc","minute" if branch=="M" else "hour")]
    parts.append(named(cylinder_x(2,4,x,0,roller_z)-cylinder_x(1.1,6,x,0,roller_z),f"DE{branch}_roller","steel"))
    arm_x=sign*(p["detent_plane_x"]+4)
    bracket_x=x
    foot_x=sign*(p["detent_plane_x"]-4)
    spring_x=sign*(p["detent_plane_x"]+3.1)
    arm = bd.Pos(arm_x, -9, (pivot_z+roller_z)/2)*bd.Box(2.6,23,8)
    arm -= cylinder_x(1.15,8,arm_x,pivot_y,pivot_z)
    arm -= cylinder_x(1.15,8,arm_x,0,roller_z)
    parts.append(named(arm,f"DE{branch}_pivot_arm","bushing"))
    parts.append(named(cylinder_x(1,6.5,sign*(p["detent_plane_x"]+2.5),0,roller_z),f"DE{branch}_roller_pin","steel"))
    parts.append(named(cylinder_x(1,8,sign*(p["detent_plane_x"]+2),pivot_y,pivot_z),f"DE{branch}_pivot_pin","steel"))
    bracket=bd.Pos(bracket_x,pivot_y,(pivot_z+6)/2)*bd.Box(4,10,pivot_z-6)
    bracket+=cylinder_x(4,4,bracket_x,pivot_y,pivot_z)
    bracket+=bd.Pos(foot_x,pivot_y,9)*bd.Box(13.6,28,6)
    bracket+=bd.Pos(sign*(p["detent_plane_x"]+2),-8,15)*bd.Box(12,30,4)
    bracket-=bd.Pos(spring_x,2,15)*bd.Cylinder(2.2,8)
    bracket-=cylinder_x(1.15,12,bracket_x,pivot_y,pivot_z)
    for dy in (-10,10):
        bracket-=bd.Pos(foot_x,pivot_y+dy,9)*bd.Cylinder(1.7,12)
        bracket-=bd.Pos(foot_x,pivot_y+dy,26)*bd.Cylinder(3.2,28)
    parts.append(named(bracket,f"DE{branch}_bracket"))
    arm_bottom=(pivot_z+roller_z)/2-4
    spring=bd.Pos(spring_x,2,18.38)*bd.Rot(0,0,-90)*wire_spring(2.5,.38,6,(arm_bottom-18-.76)/6)
    parts.append(named(spring,f"DE{branch}_compression_spring","spring"))
    adjust=bd.Pos(spring_x,2,14)*bd.Cylinder(2,8)
    adjust+=bd.Pos(spring_x,2,11.5)*bd.Cylinder(4,2)
    adjust+=bd.Pos(spring_x,2,17.5)*bd.Cylinder(4,1)
    parts.append(named(adjust,f"DE{branch}_preload_screw","steel"))
    parts.append(named(place_axial(knob(),sign*108,0,z),f"K{branch}_forward_setting_knob","hour" if branch=="H" else "minute"))
    # Separate, slotted release finger: a geometric starting point, not tuned release.
    rail=bd.Pos(sign*12,64,z+20)*bd.Box(3,60,14)
    rail+=bd.Pos(sign*12,89,(z+32)/2)*bd.Box(3,6,z+8)
    rail+=bd.Pos(sign*12,89,9)*bd.Box(16,20,6)
    for dz in (-3.5,3.5):
        rail-=bd.Pos(sign*12,64,z+20+dz)*bd.Rot(0,90,0)*bd.Rot(0,0,90)*bd.extrude(bd.SlotOverall(50,3.4),amount=4,both=True)
    for y in (83,95):rail-=bd.Pos(sign*12,y,9)*bd.Cylinder(1.7,12)
    finger=bd.Pos(sign*20.5,82,z+20)*bd.Box(14,8,12)
    for dz in (-3.5,3.5):finger-=cylinder_x(1.7,18,sign*20.5,82,z+20+dz)
    parts.append(named(rail,f"R{branch}_release_adjustment_rail"))
    parts.append(named(finger,f"R{branch}_release_finger_RETRACTED", "hour" if branch=="H" else "minute"))
    return group("DetentM" if branch=="M" else "DetentH",parts)


def sensors():
    p=values()
    parts=[]
    for sign, branch in ((1,"H"),(-1,"M")):
        x=sign*122
        holder=bd.Pos(x,0,(p['axis_height']+24)/2)*bd.Box(3,24,p['axis_height']+12)
        holder+=bd.Pos(x,0,9)*bd.Box(28,32,6)
        holder-=cylinder_x(5,8,x,0,p["axis_height"])
        for y in (-8,8):
            holder-=bd.Pos(x+sign*9,y,9)*bd.Cylinder(1.7,12)
        cap=bd.Cylinder(7,8)-bd.Pos(0,0,-2)*bd.Cylinder(4.1,5)
        cap-=bd.Pos(0,0,3)*bd.Cylinder(3.1,3)
        parts.append(named(holder,f"S{branch}_adjustable_encoder_pedestal"))
        if sign<0:cap=bd.Rot(180,0,0)*cap
        parts.append(named(place_axial(cap,sign*116,0,p["axis_height"]),f"S{branch}_magnet_cap","bushing"))
        parts.append(named(cylinder_x(3,2,sign*119,0,p["axis_height"]),f"S{branch}_diametric_magnet_ENVELOPE","steel"))
        pcb=bd.Pos(x+sign*2.5,0,p["axis_height"])*bd.Box(1.6,20,20)
        parts.append(named(pcb,f"S{branch}_absolute_encoder_PCB_ENVELOPE","pcb"))
        # Mechanical position for an independent optical home vane near the flange.
        vane=bd.Pos(sign*(p["detent_plane_x"]-2.5),34,p["axis_height"])*bd.Box(2,8,10)
        parts.append(named(vane,f"S{branch}_unique_home_vane","minute" if branch=="M" else "hour"))
    return group("Sensors",parts)


def guards():
    p=values()
    parts=[]
    for sign,branch in ((1,"H"),(-1,"M")):
        x=sign*94
        panel=bd.Pos(x,-52,p["axis_height"])*bd.Box(1.6,228,128)
        panel-=cylinder_x(19,5,x,0,p["axis_height"])
        panel-=cylinder_x(5,5,x,p["input_axis_y"],p["axis_height"])
        obj=named(panel,f"G{branch}_removable_side_panel","#B9D8DA")
        obj.color=srgb("#B9D8DA",.18)
        parts.append(obj)
    return group("Guards",parts)


def coupon_plate():
    p=values()
    parts=[]
    # Independent assemblies laid out in XY, axis Z, for inspection/bench work.
    for index,(branch,teeth) in enumerate((("M",24),("M",36),("M",48),("H",36))):
        # All test rings use the smaller 40T envelope, independent of the clock frame.
        components=clutch_components(1 if branch=="M" else -1,teeth,40)
        cx=(index%2)*90
        cy=(index//2)*90
        for role,shape in components.items():
            parts.append(named(bd.Pos(cx,cy,0)*shape,f"CP_{branch}{teeth}_{role}","minute" if branch=="M" else "hour"))
    # 8 mm shaft-fit ladder, explicitly 0.15/0.20/0.25/0.30 mm radial clearance.
    ladder=bd.Pos(45,-55,3)*bd.Box(92,18,6)
    for index,clearance in enumerate((.15,.20,.25,.30)):
        ladder-=bd.Pos(11+index*23,-55,3)*bd.Cylinder(4+clearance,10)
    parts.append(named(ladder,"CP_8mm_fit_ladder","bushing"))
    parts.append(named(bd.Pos(140,-55,3)*bd.Rot(90,0,0)*flap_blank(),"CP_flap_hinge_blank","flap"))
    return group("Concept_Only_Coupons",parts)


def clutch_rig():
    p=values()
    base=bd.Pos(0,0,3)*bd.Box(118,100,6)
    parts=[named(base,"TR_base")]
    for x in (-44,44):
        post=bd.Pos(x,0,27)*bd.Box(6,34,42)
        post+=cylinder_x(16,6,x,0,48)
        post-=cylinder_x(4.25,10,x,0,48)
        parts.append(named(post,f"TR_support_{'L' if x<0 else 'R'}"))
    parts.append(named(cylinder_x(4,100,0,0,48),"TR_input_shaft","steel"))
    parts.append(place_axial(clutch_group("M"),0,0,48))
    parts.append(named(place_axial(knob(),-34,0,48),"TR_input_knob","minute"))
    # Output loading lever keyed to the ring's cover bolt circle.
    lever=bd.Pos(0,34,9.65)*bd.Box(8,34,4)
    lever+=bd.Pos(0,14,9.65)*bd.Box(60,10,4)
    lever+=bd.Pos(0,50,9.65)*ring(6,2.5,4)
    for a in (math.radians(30),math.radians(150)):
        lever-=bd.Pos(28*math.cos(a),28*math.sin(a),9.65)*bd.Cylinder(1.65,8)
    parts.append(named(place_axial(lever,0,0,48),"TR_output_load_lever","hour"))
    return group("Clutch_Test_Rig_concept_only",parts)
