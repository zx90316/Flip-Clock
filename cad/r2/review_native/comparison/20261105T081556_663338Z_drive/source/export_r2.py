"""Export finite-force R2 model. Gear, ratchet and detent working faces are CAD.

No output actuator, prescribed output angle, gear equality or ideal one-way joint.
Belt/motor are a lumped finite input actuator; belt elasticity is NOT simulated.
"""
from __future__ import annotations
from collections import defaultdict
import hashlib
import json
import math
from pathlib import Path
import sys
import xml.etree.ElementTree as ET
import numpy as np

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT.parent / "simulation"))
from export_model import Exporter as Utilities, fmt, RY, rx, rz
from collision import convex_regions
sys.path.insert(0, str(ROOT / "src"))
import r2_geometry as g
from cadgen import read_scene, build123d as bd


def sha(path):
    return hashlib.sha256(path.read_bytes()).hexdigest()


class Exporter(Utilities):
    def __init__(self):
        self.p = g.config(); self.out = ROOT / "simulation" / "generated" / "full"
        self.assets_dir = self.out / "assets"; self.assets_dir.mkdir(parents=True, exist_ok=True)
        self.root = ET.Element("mujoco", model="FC-R2_Desktop_real_contacts")
        ET.SubElement(self.root, "compiler", angle="radian", inertiafromgeom="false", meshdir="assets", autolimits="true")
        opt = ET.SubElement(self.root, "option", timestep=".00005", gravity="0 0 -9.81", integrator="implicitfast", solver="Newton", cone="pyramidal", jacobian="dense", iterations="100", tolerance="1e-10")
        ET.SubElement(opt, "flag", filterparent="disable", energy="enable", autoreset="disable", multiccd="enable", nativeccd="disable")
        ET.SubElement(self.root, "size", memory="256M")
        defaults = ET.SubElement(self.root, "default")
        ET.SubElement(defaults, "geom", condim="3", friction=".25 .001 .00001", solref=".0006 1", solimp=".9 .95 .0001", margin="0", density="0")
        ET.SubElement(defaults, "joint", type="hinge", axis="1 0 0", limited="false", damping=".000002")
        visual = ET.SubElement(self.root, "visual")
        ET.SubElement(visual, "global", offwidth="1280", offheight="720")
        ET.SubElement(visual, "quality", shadowsize="2048", offsamples="4")
        ET.SubElement(self.root, "statistic", center="0 -.029 .060", extent=".24")
        self.asset = ET.SubElement(self.root, "asset"); self.world = ET.SubElement(self.root, "worldbody")
        ET.SubElement(self.world, "light", pos=".2 .3 .6", dir="-.2 -.3 -.6", diffuse=".8 .8 .8", ambient=".45 .45 .45")
        ET.SubElement(self.world, "light", pos="-.3 -.2 .4", dir=".3 .2 -.4", diffuse=".4 .4 .4")
        ET.SubElement(self.world, "geom", name="floor", type="plane", size="1 1 .01", pos="0 0 -.003", rgba=".94 .94 .92 1", group="0")
        self.nodes = {"world": self.world}; self.origins = {"world": np.zeros(3)}
        self.bodies = {}; self.profiles = {}; self.registry = []; self.profile_reports = {}; self.spring_sites = []; self.parts = defaultdict(list)
        self.scene = read_scene(str(ROOT / "STEP" / "assembly.step"))
        self.mass = {r["ref"]: r for r in json.loads((ROOT / "reports" / "mass_properties.json").read_text())["parts"]}
        def walk(nodes, path=()):
            for leaf in nodes:
                chain = path + (leaf.label or "",)
                if leaf.children:
                    yield from walk(leaf.children, chain)
                else:
                    yield leaf, chain
        self.leaves = list(walk(self.scene.roots))
        for b in ("M", "H"):
            axle = next(n for n, _ in self.leaves if n.label == "D" + b + "_shaft_ENVELOPE").shape()
            if abs(axle.center(bd.CenterOf.MASS).Y - g.axis_y(b)) > 1e-5:
                raise RuntimeError("Saved CAD has stale " + b + " axis; rebuild and check it")

    def owner(self, label, chain):
        for item in chain:
            if len(item) == 5 and item[:2] in ("FM", "FH") and item[3:].isdigit(): return item
        for b in ("M", "H"):
            if label.startswith("D" + b + "_") or label in ("T" + b + "_output_gear", "DE" + b + "_cam", "K" + b + "_service_knob", "S" + b + "_magnet_cap", "S" + b + "_magnet_ENVELOPE"): return "drum_" + b
            if label in ("C" + b + "_carrier", "C" + b + "_pin_ENVELOPE"): return "input"
            if label == "C" + b + "_pawl": return "pawl_" + b
            if label.startswith("C" + b + "_"): return "ring_" + b
            if label in ("DE" + b + "_arm", "DE" + b + "_roller_pin_ENVELOPE"): return "arm_" + b
            if label == "DE" + b + "_roller_ENVELOPE": return "roller_" + b
        if label in ("I_common_shaft_ENVELOPE", "I_input_pulley_ENVELOPE"): return "input"
        if label == "T_idler": return "idler"
        if label in ("TH_idler_0", "TH_idler_1"): return "h_idler_" + label[-1]
        return "world"

    def profile(self, name, face):
        if name not in self.profiles:
            cache = ROOT / "simulation" / "generated" / "profile_cache"; cache.mkdir(parents=True, exist_ok=True)
            digest = hashlib.sha256((ROOT / "src" / "r2_geometry.py").read_bytes() + (ROOT / "parameters.json").read_bytes() + name.encode()).hexdigest()[:16]
            file = cache / (name + "_" + digest + ".json")
            if file.exists():
                data = json.loads(file.read_text()); regions = [np.asarray(r) for r in data["regions"]]; report = data["report"]
            else:
                regions, report = convex_regions(face)
                file.write_text(json.dumps({"regions": [r.tolist() for r in regions], "report": report}), encoding="utf-8")
            self.profiles[name] = regions; self.profile_reports[name] = report
            print("profile", name, report["regions"], flush=True)
        return self.profiles[name]

    def build_bodies(self):
        p = self.p; y = p["input_y"]; z = p["axis_z"]
        self.body("input", [0, y, z], joint="I", armature=p["motor"]["reflected_armature_kg_m2"], damping=".0001")
        for b in ("M", "H"):
            s = g.sign(b); x = s * p["gear_x"]; d = g.direction(b)
            self.body("ring_" + b, [x, y, z], joint="O" + b, damping=".000005", frictionloss=".000002")
            self.body("pawl_" + b, [x + 1.9, y - 3 * d, z - 9.2], parent="input", joint="P" + b, stiffness=".001", springref=fmt(-d * .10), damping=".000005")
        self.body("idler", [-50, -36, z], joint="idler", damping=".000002")
        for i, (yy, zz) in enumerate(g.hour_train()["centres"]):
            self.body("h_idler_" + str(i), [50, yy, zz], joint="HI" + str(i), damping=".000002")
        for b in ("M", "H"):
            s = g.sign(b); cx = s * p["drum_x"]; rz_ = z - g.roller_radius(b)
            yy = g.axis_y(b)
            self.body("drum_" + b, [cx, yy, z], joint=b, damping=".00002", frictionloss=".000003")
            self.body("arm_" + b, [s * 62, yy - 18, rz_ - 3], joint="D" + b, damping=".000002")
            self.body("roller_" + b, [s * 58, yy, rz_], parent="arm_" + b, joint="R" + b, damping=".0000001")
            for k in range(g.count(b)):
                angle = 360 * k / g.count(b); a = math.radians(angle); tilt = angle - 90 + p["flap"]["initial_fan_tilt_deg"]
                origin = [cx, yy + g.pivot_r(b) * math.cos(a), z + g.pivot_r(b) * math.sin(a)]
                self.body(f"F{b}_{k:02}", origin, parent="drum_" + b, quat=[math.cos(math.radians(tilt) / 2), math.sin(math.radians(tilt) / 2), 0, 0], joint=f"F{b}_{k:02}", damping=".0000003", frictionloss=".00000005")

    def inertias(self):
        for body in self.bodies:
            transform = np.eye(3)
            if body.startswith("F"):
                b = body[1]; k = int(body[3:]); transform = rx(360 * k / g.count(b) - 90 + self.p["flap"]["initial_fan_tilt_deg"])
            records = []
            for leaf, _ in self.parts[body]:
                row = self.mass[leaf.ref]; m = row["mass_kg"]; c = transform.T @ (np.asarray(row["com_m"]) - self.origins[body] * .001)
                i = transform.T @ np.asarray(row["inertia_kg_m2"]) @ transform; records.append((m, c, i))
            total = sum(m for m, _, _ in records)
            if total <= 0: raise ValueError("Missing saved-CAD mass: " + body)
            center = sum(m * c for m, c, _ in records) / total; tensor = np.zeros((3, 3))
            for m, c, i in records:
                d = c - center; tensor += i + m * (np.eye(3) * np.dot(d, d) - np.outer(d, d))
            if np.min(np.linalg.eigvalsh(tensor)) <= 0: raise ValueError("Invalid inertia: " + body)
            ET.SubElement(self.nodes[body], "inertial", mass=fmt(total), pos=fmt(center), fullinertia=fmt([tensor[0, 0], tensor[1, 1], tensor[2, 2], tensor[0, 1], tensor[0, 2], tensor[1, 2]]))
            self.bodies[body].update(mass_kg=total, com_m=center.tolist(), inertia_com_kg_m2=tensor.tolist())

    def visuals(self):
        color_map = {k: tuple(bd.Color(v).to_tuple()) for k, v in []}  # All colors below are explicit linear-ish display values.
        for body, leaves in self.parts.items():
            if body.startswith("F"): continue
            buckets = defaultdict(list)
            for leaf, _ in leaves:
                label = leaf.label
                if "spring" in label.lower(): continue
                color = (.15, .20, .23, 1)
                if "ENVELOPE" in label: color = (.62, .66, .68, 1)
                if "PCB" in label: color = (.12, .34, .22, 1)
                if "belt" in label.lower(): color = (.07, .08, .08, 1)
                if body.endswith("_M"): color = (.20, .42, .40, 1)
                if body.endswith("_H"): color = (.58, .41, .20, 1)
                if label in ("A00_single_base", "A01_inverted_print_hood", "A03_rear_panel"): color = (.83, .79, .71, 1)
                if label.startswith("A05_colon_"): color = (.94, .91, .82, 1)
                group_ = 4 if label in ("A01_inverted_print_hood", "A02_front_panel", "A03_rear_panel", "A04_display_bezel") or label.startswith("A05_colon_") else 2
                buckets[(color, group_)].append(leaf.shape())
            for k, ((color, group_), shapes) in enumerate(buckets.items()): self.add_visual_mesh(body, body + "_" + str(k), shapes, color, group_)

    def mechanics(self):
        p = self.p; y = p["input_y"]; z = p["axis_z"]
        for b in ("M", "H"):
            x = g.sign(b) * 50; n = 40 if b == "M" else 60; d = g.direction(b)
            profile = g.gear_profile(n, 1.2, .22) - g.ratchet_profile(b)
            self.prisms("ring_" + b, "clutch_" + b, profile, 6, [x, y, z])
            self.cylinder("ring_" + b, "back_" + b, [x - 4, y, z], 1.2 * n / 2 - 1.7, 2)
            self.cylinder("ring_" + b, "neck_" + b, [x - 6, y, z], 9.5, 6)
            self.prisms("ring_" + b, "cover", bd.Circle(21.2) - bd.Circle(8.4), 2, [x + 7.4, y, z])
            self.cylinder("input", "carrier_disc_" + b, [x - 1.3, y, z], 12.6, 2.4)
            self.cylinder("input", "carrier_hub_" + b, [x + 2.2, y, z], 6.8, 9.4)
            self.prisms("input", "heel_stop_" + b, g.engagement_stop_profile(b), 3.8, [x, y, z], z_mm=1.4)
            self.prisms("pawl_" + b, "pawl_" + b, g.pawl_profile(b), 2.8, [x, y, z], z_mm=1.9)
        self.prisms("idler", "idler", g.gear_profile(20, 1.2, .22), 6, [-50, -36, z], rotation=RY @ rz(9))
        ht = g.hour_train()
        for i, ((yy, zz), phase) in enumerate(zip(ht["centres"], ht["phases"])):
            self.prisms("h_idler_" + str(i), "hour_idler_" + str(i), g.gear_profile(20, 1.2, .22), 6, [50, yy, zz], rotation=RY @ rz(phase))
        for b in ("M", "H"):
            s = g.sign(b); cx = s * p["drum_x"]; x = s * 50; yy = g.axis_y(b)
            self.prisms("drum_" + b, "gear_" + b, g.gear_profile(40, 1.2, .22), 6, [x, yy, z], rotation=RY @ rz(0 if b == "M" else ht["output_phase"]))
            self.cylinder("drum_" + b, "core_" + b, [cx, yy, z], 8 if b == "H" else 10, 34.8)
            for fs in (-1, 1):
                self.cylinder("drum_" + b, f"flange_{b}_{fs}", [cx + fs * 18.6, yy, z], g.flange_r(b), 2.4)
                self.cylinder("drum_" + b, f"collar_{b}_{fs}", [cx + fs * 15.6, yy, z], 13 if b == "H" else 16, 3.6)
            self.prisms("drum_" + b, "detent_" + b, g.detent_profile(b), 3, [s * 58, yy, z])
            rz_ = z - g.roller_radius(b); pz = rz_ - 3
            self.cylinder("roller_" + b, "roller_" + b, [s * 58, yy, rz_], 2, 4)
            self.box("arm_" + b, "arm_" + b, [s * 62, yy - 9, (pz + rz_) / 2], [2.8, 23, 8])
            down = np.array([s * 61.1, yy + 2, 10.5]); up = np.array([s * 61.1, yy + 2, (pz + rz_) / 2 - 4])
            ET.SubElement(self.world, "site", name="spring_base_" + b, pos=fmt(down * .001), size=".0004", group="2")
            ET.SubElement(self.nodes["arm_" + b], "site", name="spring_tip_" + b, pos=fmt((up - self.origins["arm_" + b]) * .001), size=".0004", group="2")
            self.spring_sites.append({"branch": b, "base": "spring_base_" + b, "tip": "spring_tip_" + b, "body": "arm_" + b,
                                      "stiffness_N_m": p["detent"].get("H_spring_k_N_m", p["detent"]["spring_k_N_m"]) if b == "H" else p["detent"]["spring_k_N_m"], "damping_N_s_m": .04, "free_length_m": (up[2] - down[2] + p["detent"]["preload_mm"]) * .001, "max_force_N": 3})
        tendon = ET.SubElement(self.root, "tendon")
        for spec in self.spring_sites:
            td = ET.SubElement(tendon, "spatial", name="compression_" + spec["branch"], width=".0004", rgba=".7 .55 .25 1")
            ET.SubElement(td, "site", site=spec["base"]); ET.SubElement(td, "site", site=spec["tip"])

    def flap_geometries(self):
        path = self.assets_dir / "flap_blank.stl"; bd.export_stl(g.flap_blank(), str(path), tolerance=.01, angular_tolerance=.08)
        ET.SubElement(self.asset, "mesh", name="flap_blank", file=path.name, scale=".001 .001 .001", maxhullvert="8")
        f = self.p["flap"]
        for b in ("M", "H"):
            for k in range(g.count(b)):
                body = f"F{b}_{k:02}"
                ET.SubElement(self.nodes[body], "geom", name="v_" + body, type="mesh", mesh="flap_blank", group="2", rgba=".025 .035 .045 1", contype="0", conaffinity="0")
                self.geom(body, body + "_plate", "box", [0, f["panel_center_y"], f["length"] / 2], [f["width"] / 2, f["thickness"] / 2, f["length"] / 2])
                # Only the exposed spine collides: the end trunnions are bearing
                # interiors replaced by the hinge, never contact with filled flange holes.
                radius = f["trunnion_d"] / 2; end_angle = math.acos(f["pin_flat_y"] / radius)
                begin_angle = math.acos(f["pin_front_flat_y"] / radius)
                angles = np.r_[np.linspace(begin_angle, end_angle, 33), np.linspace(2 * math.pi - end_angle, 2 * math.pi - begin_angle, 33)]
                section = [(radius * math.cos(a), radius * math.sin(a)) for a in angles]
                vertices = [(x, yy, zz) for x in (-f["width"] / 2, f["width"] / 2) for yy, zz in section]
                mesh = body + "_D_spine"
                ET.SubElement(self.asset, "mesh", name=mesh, vertex=fmt(np.asarray(vertices) * .001), maxhullvert="-1")
                ET.SubElement(self.nodes[body], "geom", name="c_" + mesh, type="mesh", mesh=mesh, group="3", rgba="0 0 0 0")
                self.registry.append({"geom": "c_" + mesh, "body": body, "representation": "convex_double_flat_spine_66_samples"})
                for side, (val, upper) in enumerate(((k, True), ((k + 1) % g.count(b), False))):
                    for j, solid in enumerate(g.digit_boxes(val, upper, .05).solids()):
                        box = solid.bounding_box(); c = (box.min + box.max) * .5
                        self.geom(body, f"{body}_digit_{side}_{j}", "box", [c.X, f["panel_center_y"] + (f["thickness"] / 2 + .025) * (1 if upper else -1), c.Z], [box.size.X / 2, .025, box.size.Z / 2], rgba=[.94, .91, .82, 1], group=0, collide=False)

    def frame_collisions(self):
        p = self.p; z = p["axis_z"]
        self.box("world", "base", [0, -29, 2.4], [190, 174, 4.8])
        for s in (-1, 1):
            yy = g.axis_y("H" if s > 0 else "M"); cy = (yy - 72) / 2
            for y in (yy, -72): self.box("world", f"support_{s}_{y}", [s * p["frame_x"], y, (z + 9.6) / 2], [6.4, 27, z - 9.6])
            self.box("world", f"beam_{s}", [s * p["frame_x"], cy, z], [6.4, yy + 72, 14])
            self.box("world", f"frame_foot_{s}", [s * p["frame_x"], cy, 7.2], [6.4, 150 if s > 0 else 128, 4.8])
            self.box("world", f"encoder_post_{s}", [s * 88, yy, (z + 4.8) / 2], [2.4, 22, z - 4.8])
            self.box("world", "center_pedestal_" + str(s), [0, yy, (z + 4.8) / 2], [6, 17, z - 4.8])
        self.box("world", "idler_pedestal", [-59, -36, (z + 4.8) / 2], [6.4, 12, z - 4.8])
        for i, (yy, zz) in enumerate(g.hour_train()["centres"]):
            ymax = min(yy + 6, -1.7)
            self.box("world", "H_idler_pedestal_" + str(i), [62.8, (yy - 6 + ymax) / 2, (zz + 4.8) / 2], [6, ymax - yy + 6, zz - 4.8])
        for b in ("M", "H"):
            s = g.sign(b); rz_ = z - g.roller_radius(b); pz = rz_ - 3
            yy = g.axis_y(b)
            self.box("world", "detent_post_" + b, [s * 58, yy - 18, (pz + 4.8) / 2], [4, 10, pz - 4.8])
            self.box("world", "detent_foot_" + b, [s * 52.5, yy - 5, 7.2], [14, 28, 4.8])
            self.box("world", "spring_ledge_" + b, [s * 60, yy - 8, 9], [11, 30, 3])
            self.cylinder("world", "retainer_" + b, [s * 24, p["retainer"]["y"], p["retainer"]["z"]], .5, 40)
            for side in (-1, 1): self.box("world", f"wire_clamp_{b}_{side}", [s * 24 + side * 19, 50.2, 73], [3, 10, 6])
        # Hood remains solid in cutaway rendering. Main panels use their real
        # CAD apertures; never a solid box across the display opening.
        self.box("world", "hood_left", [-93.8, -29, 61.2], [2.4, 150, 112.8])
        self.box("world", "hood_right", [93.8, -29, 61.2], [2.4, 150, 112.8])
        self.box("world", "hood_roof", [0, -29, 118.8], [166, 174, 2.4])
        self.box("world", "rear_panel", [0, -114.4, 61.2], [165.2, 2.4, 112])
        # Front upper/lower rails, side cheeks and centre web around two holes.
        self.box("world", "front_upper", [0, 56.4, 97.2], [165.2, 2.4, 40.0])
        self.box("world", "front_lower", [0, 56.4, 22], [165.2, 2.4, 33.6])
        for x in (-62.4, 62.4): self.box("world", "front_cheek_" + str(x), [x, 56.4, 58], [40.4, 2.4, 38.4])
        self.box("world", "front_center", [0, 56.4, 58], [11.6, 2.4, 38.4])

    def finish(self):
        for leaf, chain in self.leaves: self.parts[self.owner(leaf.label, chain)].append((leaf, chain))
        self.build_bodies(); self.inertias(); self.visuals(); self.mechanics(); self.flap_geometries(); self.frame_collisions()
        actuator = ET.SubElement(self.root, "actuator")
        limit = self.p["motor"]["stall_torque_Nm"]
        ET.SubElement(actuator, "motor", name="single_finite_input_torque", joint="I", gear="1", ctrlrange=fmt([-limit, limit]), forcerange=fmt([-limit, limit]))
        ET.indent(self.root, space="  "); path = self.out / "model.xml"; ET.ElementTree(self.root).write(path, encoding="utf-8", xml_declaration=True)
        sources = {str(p.relative_to(ROOT)).replace("\\", "/"): sha(p) for p in (ROOT / "src" / "r2_geometry.py", ROOT / "parameters.json", ROOT / "STEP" / "assembly.step", ROOT / "reports" / "mass_properties.json", Path(__file__))}
        manifest = {"design": "FC-R2", "units": "SI", "sources_sha256": sources, "bodies": self.bodies, "compression_springs": self.spring_sites, "motor": self.p["motor"], "profiles": self.profile_reports,
                    "collision_geoms": self.registry, "model_sha256": sha(path), "assumptions": ["Only one finite input torque actuator; no equality constraints, ideal clutches or output actuation.",
                    "Bearing and pin interiors use hinge joints; exposed flap spine and plates, working teeth and retainers collide.",
                    "Nonworking lightening holes and glyph pockets are filled in collision proxies; masses use the saved CAD solids.",
                    "Belt and gearbox represented by finite reflected input inertia and torque only, not belt elasticity, tooth skip, motor phases or gearbox backlash.",
                    "Coulomb friction, proposed solid densities and spring rates are unmeasured.", "Front-corner rounds and screw holes are conservatively filled in fixed collision proxies."],
                    "physics_verified": False, "hardware_verified": False, "manufacturing_ready": False}
        (self.out / "manifest.json").write_text(json.dumps(manifest, indent=2), encoding="utf-8")
        print("EXPORTED", len(self.bodies), "bodies", len(self.registry), "collision geoms", flush=True)
        from compact_model import compact_model
        compact_model(self.out)
        updated = json.loads((self.out / "manifest.json").read_text())
        updated["model_sha256"] = sha(path)
        (self.out / "manifest.json").write_text(json.dumps(updated, indent=2), encoding="utf-8")
        return path


if __name__ == "__main__":
    Exporter().finish()
