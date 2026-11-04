"""Refresh solver/viewer options without changing authored CAD or contacts."""
import hashlib
import json
from pathlib import Path
import xml.etree.ElementTree as ET
import mujoco as mj


def refresh_options(directory):
    directory=Path(directory);tree=ET.parse(directory/"model.xml");root=tree.getroot()
    option=root.find("option");option.set("solver","Newton");option.set("cone","pyramidal");option.set("jacobian","dense")
    option.set("ccd_tolerance","1e-9");option.set("ccd_iterations","100")
    flags=option.find("flag");flags.set("diagexact","enable");flags.set("nativeccd","disable")
    geom=root.find("default/geom");geom.set("solref",".0006 1");geom.set("solimp",".9 .95 .0001")
    visual=root.find("visual");visual.find("global").set("azimuth","-70")
    visual.find("scale").set("contactwidth",".06");visual.find("scale").set("contactheight",".02")
    visual.find("rgba").set("contactpoint","1 .1 .08 1")
    if root.find("asset/texture[@name='physics_sky']") is None:
        ET.SubElement(root.find("asset"),"texture",name="physics_sky",type="skybox",builtin="gradient",rgb1=".88 .92 .96",rgb2=".97 .98 1",width="512",height="512")
    ET.indent(root,space="  ");tree.write(directory/"model.xml",encoding="utf-8",xml_declaration=True)
    manifest=json.loads((directory/"manifest.json").read_text(encoding="utf-8"));manifest["version"]=mj.__version__
    manifest["xml_sha256"]=hashlib.sha256((directory/"model.xml").read_bytes()).hexdigest()
    manifest["solver_options"]={"diagexact":True,"solver":"Newton","cone":"pyramidal","jacobian":"dense","narrowphase":"libccd","ccd_tolerance_m":1e-9,"contact_time_constant_s":.0006}
    manifest["solver_rationale"]="Fixed-axis gears have near-zero compile-time translational body_invweight0; exact current J M^-1 J^T diagonal prevents falsely hard contacts. No masses or output angles are modified."
    manifest["solver_reference"]="https://mujoco.readthedocs.io/en/3.17.0/computation/index.html#impedance"
    (directory/"manifest.json").write_text(json.dumps(manifest,indent=2),encoding="utf-8")
    print("Refreshed MuJoCo "+mj.__version__+" with exact contact inertia: "+str(directory),flush=True)
