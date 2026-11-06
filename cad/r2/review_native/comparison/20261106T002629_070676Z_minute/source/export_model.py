"""Build MuJoCo bodies from the saved, newly authored FC-R1 CAD.

Working gear/ratchet/detent outlines are convex decompositions of native CAD
faces, not convex hulls of complete gears. All dimensions convert mm -> m.
Shaft and trunnion internals use revolute-bearing abstractions; external flap
barrel surfaces, plates, raised digits, drum flanges, pawls and stops collide.
"""
from __future__ import annotations
from collections import defaultdict
import hashlib
import json
import math
from pathlib import Path
import re
import sys
import xml.etree.ElementTree as ET
import numpy as np

ROOT=Path(__file__).resolve().parents[1]
sys.path.insert(0,str(ROOT/"src"))
from cadgen import read_scene, build123d as bd
import geometry as g
from settings import values
from collision import convex_regions,prism_vertices

RY=np.array([[0.,0.,1.],[0.,1.,0.],[-1.,0.,0.]])
RGB={"frame":(.10,.15,.20,1),"M":(.08,.57,.59,1),"H":(.88,.58,.16,1),
     "steel":(.58,.65,.70,1),"ivory":(.86,.82,.70,1),"pcb":(.08,.33,.18,1)}


def fmt(value):
    if isinstance(value,(str,int,float)):return str(value)
    return " ".join(f"{float(v):.12g}" for v in np.asarray(value).reshape(-1))


def rx(degrees):
    a=math.radians(degrees);c,s=math.cos(a),math.sin(a)
    return np.array([[1.,0,0],[0,c,-s],[0,s,c]])


def rz(degrees):
    a=math.radians(degrees);c,s=math.cos(a),math.sin(a)
    return np.array([[c,-s,0],[s,c,0],[0,0,1.]])


def flat_outer(shape,z):
    candidates=[f for f in shape.faces() if f.geom_type==bd.GeomType.PLANE and abs(f.center().Z-z)<1e-5 and abs(f.normal_at().Z)>.99]
    face=max(candidates,key=lambda f:f.area)
    return bd.Face(face.outer_wire())


def flat_face(shape,z):
    """Preserve inner wires, especially the working clearance of clutch covers."""
    candidates=[f for f in shape.faces() if f.geom_type==bd.GeomType.PLANE and abs(f.center().Z-z)<1e-5 and abs(f.normal_at().Z)>.99]
    return max(candidates,key=lambda f:f.area)


class Exporter:
    def __init__(self,scope):
        self.scope=scope;self.p=values();self.out=ROOT/"simulation"/"generated"/scope
        self.assets_dir=self.out/"assets";self.assets_dir.mkdir(parents=True,exist_ok=True)
        self.root=ET.Element("mujoco",model="FC-R1_actual_contact_"+scope)
        ET.SubElement(self.root,"compiler",angle="radian",inertiafromgeom="false",meshdir="assets",autolimits="true")
        option=ET.SubElement(self.root,"option",timestep=".00002",gravity="0 0 -9.81",integrator="implicitfast",solver="CG",cone="pyramidal",jacobian="dense",iterations="100",tolerance="1e-10",ls_iterations="20")
        ET.SubElement(option,"flag",filterparent="disable",energy="enable",autoreset="disable",multiccd="enable",nativeccd="disable")
        ET.SubElement(self.root,"size",memory="256M")
        defaults=ET.SubElement(self.root,"default")
        ET.SubElement(defaults,"geom",condim="3",friction=".25 .001 .00001",solref=".0006 1",solimp=".9 .95 .0001",margin="0",density="0")
        ET.SubElement(defaults,"joint",type="hinge",axis="1 0 0",limited="false",damping=".000002")
        visual=ET.SubElement(self.root,"visual")
        ET.SubElement(visual,"global",offwidth="1280",offheight="720",azimuth="75",elevation="-24")
        ET.SubElement(visual,"quality",shadowsize="2048",offsamples="4")
        ET.SubElement(visual,"rgba",haze=".94 .96 .98 1")
        ET.SubElement(visual,"scale",forcewidth=".0003",contactwidth=".001",contactheight=".0004")
        ET.SubElement(self.root,"statistic",center="0 -.035 .08",extent=".32")
        self.asset=ET.SubElement(self.root,"asset");self.world=ET.SubElement(self.root,"worldbody")
        ET.SubElement(self.world,"light",pos=".2 .3 .6",dir="-.2 -.3 -.6",diffuse=".8 .8 .8",ambient=".45 .45 .45")
        ET.SubElement(self.world,"light",pos="-.3 -.2 .4",dir=".3 .2 -.4",diffuse=".4 .4 .4")
        ET.SubElement(self.world,"geom",name="floor",type="plane",size="1 1 .01",pos="0 0 -.003",rgba=".92 .94 .96 1",group="0")
        self.nodes={"world":self.world};self.origins={"world":np.zeros(3)}
        self.bodies={};self.profiles={};self.parts=defaultdict(list);self.registry=[];self.profile_reports={}
        self.spring_sites=[];self.mass_records={};self.scene=read_scene(str(ROOT/"STEP"/"assembly.step"))
        meta=json.loads((ROOT/"reports"/"mass_properties_SI.json").read_text(encoding="utf-8"))
        self.mass_records={r["ref"]:r for r in meta["parts"]}
        self.leaves=[]
        def walk(nodes,path=()):
            for node in nodes:
                chain=path+(node.label or "",)
                if node.children:walk(node.children,chain)
                else:self.leaves.append((node,chain))
        walk(self.scene.roots)
        self.omissions=[]

    def body(self,name,origin_mm,parent="world",quat=None,joint=None,**joint_options):
        origin=np.asarray(origin_mm,dtype=float)
        attrs={"name":name,"pos":fmt((origin-self.origins[parent])*.001)}
        if quat is not None:attrs["quat"]=fmt(quat)
        node=ET.SubElement(self.nodes[parent],"body",**attrs)
        ET.SubElement(node,"joint",name=joint or name+"_joint",**{k:fmt(v) for k,v in joint_options.items()})
        self.nodes[name]=node;self.origins[name]=origin;self.bodies[name]={"origin_mm":origin.tolist(),"parent":parent}
        return node

    def geom(self,body,name,kind,pos_mm,size_mm,rgba=None,group=3,quat=None,collide=True):
        attrs={"name":name,"type":kind,"pos":fmt(np.asarray(pos_mm)*.001),"size":fmt(np.asarray(size_mm)*.001),"group":str(group),"rgba":fmt(rgba or (0,0,0,0))}
        if quat is not None:attrs["quat"]=fmt(quat)
        if not collide:attrs.update(contype="0",conaffinity="0")
        ET.SubElement(self.nodes[body],"geom",**attrs)
        if collide:self.registry.append({"geom":name,"body":body,"representation":kind})

    def cylinder(self,body,name,world_mm,radius,length,collide=True):
        self.geom(body,name,"cylinder",np.asarray(world_mm)-self.origins[body],[radius,length/2],quat=[math.sqrt(.5),0,math.sqrt(.5),0],collide=collide)

    def box(self,body,name,world_mm,size_mm):
        self.geom(body,name,"box",np.asarray(world_mm)-self.origins[body],np.asarray(size_mm)/2)

    def profile(self,name,face):
        if name not in self.profiles:
            cache=ROOT/"simulation"/"generated"/"profile_cache";cache.mkdir(parents=True,exist_ok=True)
            # Include full authored geometry/config hashes: no stale collision profiles.
            face_signature=(name+"|"+str(round(sum(f.area for f in face.faces()),8))).encode()
            digest=hashlib.sha256((ROOT/"src"/"geometry.py").read_bytes()+(ROOT/"config"/"parameters.yaml").read_bytes()+(ROOT/"simulation"/"collision.py").read_bytes()+face_signature).hexdigest()[:16]
            file=cache/(name+"_"+digest+".json")
            if file.exists():
                data=json.loads(file.read_text());regions=[np.asarray(p) for p in data["regions"]];report=data["report"]
            else:
                regions,report=convex_regions(face)
                file.write_text(json.dumps({"regions":[r.tolist() for r in regions],"report":report}),encoding="utf-8")
            self.profiles[name]=regions;self.profile_reports[name]=report
            print(f"profile {name}: {report['regions']} convex pieces, area error {report['symmetric_difference_mm2']:.3g} mm2",flush=True)
        return self.profiles[name]

    def prisms(self,body,name,face,height_mm,center_world_mm,rotation=RY,z_mm=0):
        regions=self.profile(name,face)
        for index,poly in enumerate(regions):
            local=prism_vertices(poly,height_mm,z_mm)@rotation.T+np.asarray(center_world_mm)-self.origins[body]
            mesh=f"{body}_{name}_{index}"
            ET.SubElement(self.asset,"mesh",name=mesh,vertex=fmt(local*.001),maxhullvert="-1")
            ET.SubElement(self.nodes[body],"geom",name="c_"+mesh,type="mesh",mesh=mesh,group="3",rgba="0 0 0 0")
            self.registry.append({"geom":"c_"+mesh,"body":body,"representation":"native_CAD_convex_prism","profile":name})

    def add_visual_mesh(self,body,name,shapes,color,group=2):
        if not shapes:return
        delta=-self.origins[body]
        placed=[s.moved(bd.Location(tuple(delta))) for s in shapes]
        shape=bd.Compound(children=placed)
        path=self.assets_dir/(name+".stl")
        bd.export_stl(shape,str(path),tolerance=.02,angular_tolerance=.12)
        ET.SubElement(self.asset,"mesh",name="v_"+name,file=path.name,scale=".001 .001 .001",maxhullvert="8")
        ET.SubElement(self.nodes[body],"geom",name="v_"+name,type="mesh",mesh="v_"+name,group=str(group),rgba=fmt(color),contype="0",conaffinity="0")

    def classify(self,label,path):
        for item in path:
            if re.fullmatch(r"F[MH]_\d\d",item):return item
        for b in ("M","H"):
            if label.startswith("P"+b+"_") or label.startswith("D"+b+"_") or label in ("A4"+b+"_drum_gear","DE"+b+"_scallop_disc","K"+b+"_forward_setting_knob"):
                return "drum_"+b
            if label.startswith("S"+b+"_") and any(s in label for s in ("magnet_cap","diametric_magnet","unique_home_vane")):return "drum_"+b
            if label in ("DE"+b+"_pivot_arm","DE"+b+"_roller_pin"):return "arm_"+b
            if label=="DE"+b+"_roller":return "roller_"+b
            if label in ("C"+b+"_carrier","C"+b+"_pin"):return "input"
            if label=="C"+b+"_pawl":return "pawl_"+b
            if label in ("C"+b+"_output","C"+b+"_bushing","C"+b+"_cover") or "C"+b+"_posts" in path:return "ring_"+b
            if "C"+b+"_spring" in path:return "input"
        if label in ("A40M_idler","H04_idler_bushing"):return "idler"
        if label in ("A10_common_input_shaft","A11_5_to_8_coupler","E00_output_shaft_ENVELOPE"):return "input"
        return "world"

    def collect(self):
        for leaf,path in self.leaves:
            owner=self.classify(leaf.label,path)
            if self.scope=="clutch" and owner not in ("input","ring_M","pawl_M"):continue
            if self.scope=="clutch" and owner=="input":
                if leaf.label=="CH_carrier" or "CH_spring" in path or leaf.label=="CH_pin":continue
            self.parts[owner].append((leaf,path))

    def inertia(self,body,rotation=None):
        records=[]
        for leaf,path in self.parts[body]:
            row=self.mass_records[leaf.ref]
            mass=row["estimated_mass_kg"]
            com=np.asarray(row["center_of_mass_m"])-self.origins[body]*.001
            inertia=np.asarray(row["inertia_about_com_kg_m2"])
            if rotation is not None:com=rotation.T@com;inertia=rotation.T@inertia@rotation
            records.append((mass,com,inertia))
        total=sum(r[0] for r in records)
        if total<=0:raise ValueError("No CAD mass for "+body)
        center=sum(m*c for m,c,_ in records)/total
        tensor=np.zeros((3,3))
        for mass,c,i in records:
            delta=c-center;tensor+=i+mass*(np.eye(3)*np.dot(delta,delta)-np.outer(delta,delta))
        if np.min(np.linalg.eigvalsh(tensor))<=1e-15:raise ValueError("Nonpositive CAD inertia for "+body)
        full=[tensor[0,0],tensor[1,1],tensor[2,2],tensor[0,1],tensor[0,2],tensor[1,2]]
        ET.SubElement(self.nodes[body],"inertial",mass=fmt(total),pos=fmt(center),fullinertia=fmt(full))
        self.bodies[body].update(mass_kg=total,com_m=center.tolist(),inertia_com_kg_m2=tensor.tolist())

    def visuals(self):
        for body,parts in self.parts.items():
            if body.startswith("F"):continue
            by_color=defaultdict(list)
            for leaf,path in parts:
                role="_".join(path).lower();label=leaf.label or ""
                if "spring" in role:continue  # Force-equivalent spring visualization uses endpoints.
                color="frame"
                if any(s in role for s in ("shaft","_pin","_race","_shield","_roller","_screw","diametric_magnet")) or label.startswith(("B00_","B01_")) or label.startswith("E00_"):color="steel"
                elif "pcb" in role:color="pcb"
                elif "bushing" in role or "magnet_cap" in role or "pivot_arm" in role or "tpu_foot" in role:color="ivory"
                elif body.endswith("_M") or label.startswith(("CM_","A11_")):color="M"
                elif body.endswith("_H") or label.startswith("CH_"):color="H"
                if label.startswith("G") and "side_panel" in label:
                    by_color[("guard",4)].append(leaf.shape());continue
                group=4 if label in ("CM_cover","CH_cover") or "CM_posts" in path or "CH_posts" in path else 2
                by_color[(color,group)].append(leaf.shape())
            for (color,group),shapes in by_color.items():
                self.add_visual_mesh(body,body+"_"+color+"_"+str(group),shapes,(.7,.84,.86,.15) if color=="guard" else RGB[color],group)

    def build_bodies(self):
        p=self.p;y,z=p["input_axis_y"],p["axis_height"]
        self.body("input",[0,y,z],joint="I",armature=".0001",damping=".0001")
        for b in (("M",) if self.scope=="clutch" else ("M","H")):
            sign=g.branch_sign(b);x=sign*p["gear_plane_x"];direction=1 if b=="M" else -1
            self.body("ring_"+b,[x,y,z],joint="O"+b,damping=".000005",frictionloss=".000002")
            pivot=np.array([x+1.6,y-5.5*direction,z-15])
            self.body("pawl_"+b,pivot,parent="input",joint="P"+b,stiffness=".001",springref=fmt(-direction*.12),damping=".000005")
        if self.scope=="clutch":return
        self.body("idler",[-p["gear_plane_x"],y/2,z],joint="idler",damping=".000002")
        for b,count in (("M",60),("H",24)):
            sign=g.branch_sign(b);cx=sign*p["drum_center_x"]
            self.body("drum_"+b,[cx,0,z],joint=b,damping=".00002",frictionloss=".000003")
            roller_z=z-g.detent_roller_center_radius(count);pivot_z=roller_z-3
            self.body("arm_"+b,[sign*(p["detent_plane_x"]+4),-18,pivot_z],joint="D"+b,damping=".000002")
            self.body("roller_"+b,[sign*p["detent_plane_x"],0,roller_z],parent="arm_"+b,joint="R"+b,damping=".0000001")
            for k in range(count):
                angle=-360*k/count;phi=math.radians(angle)
                origin=np.array([cx,p["flap_pivot_radius"]*math.cos(phi),z+p["flap_pivot_radius"]*math.sin(phi)])
                qangle=math.radians(angle-90)/2
                self.body(f"F{b}_{k:02}",origin,parent="drum_"+b,quat=[math.cos(qangle),math.sin(qangle),0,0],joint=f"F{b}_{k:02}",damping=".0000003",frictionloss=".00000005")

    def mechanics(self):
        p=self.p;y,z=p["input_axis_y"],p["axis_height"];plane=p["gear_plane_x"]
        branches=("M",) if self.scope=="clutch" else ("M","H")
        for b in branches:
            sign=g.branch_sign(b);x=sign*plane;direction=1 if b=="M" else -1
            n=p["minute_driver_teeth"] if b=="M" else p["hour_driver_teeth"]
            profile=g.gear_profile(n,p["gear_module"],p["gear_backlash"])-g.ratchet_cavity(p["ratchet_teeth"],direction)
            self.prisms("ring_"+b,"clutch_"+b,profile,p["gear_width"],[x,y,z])
            root=p["gear_module"]*n/2-1.25*p["gear_module"]
            self.cylinder("ring_"+b,"back_"+b,[x-4,y,z],root-.2,2)
            self.cylinder("ring_"+b,"neck_"+b,[x-6,y,z],9.5,6)
            cover=g.ring(31.2,8.4,1.5)
            self.prisms("ring_"+b,"cover",flat_face(cover,.75),1.5,[x+6.9,y,z])
            self.cylinder("input","carrier_disc_"+b,[x-.9,y,z],18.5,2)
            self.cylinder("input","carrier_hub_"+b,[x+2,y,z],7.8,9.8)
            stop=(RY@np.array([17.3,-8.6*direction,1.5]))+np.array([x,y,z])
            self.box("input","carrier_stop_"+b,stop,[2.8,2,2])
            pawn=g.pawl(direction)
            self.prisms("pawl_"+b,"pawl_"+b,flat_outer(pawn,p["pawl_width"]/2),p["pawl_width"],[x,y,z],z_mm=1.6)
        if self.scope=="clutch":return
        self.prisms("idler","idler_20",g.gear_profile(20,p["gear_module"],p["gear_backlash"]),p["gear_width"],[-plane,y/2,z],rotation=RY@rz(9))
        for b,count in (("M",60),("H",24)):
            sign=g.branch_sign(b);cx=sign*p["drum_center_x"];x=sign*plane;n=p["minute_output_teeth"] if b=="M" else p["hour_output_teeth"]
            self.prisms("drum_"+b,"output_gear_"+b,g.gear_profile(n,p["gear_module"],p["gear_backlash"]),p["gear_width"],[x,0,z],rotation=RY@rz(0 if b=="M" else 180/n))
            self.cylinder("drum_"+b,"core_"+b,[cx,0,z],14,50)
            for s in (-1,1):
                self.cylinder("drum_"+b,f"flange_{b}_{s}",[cx+s*26.5,0,z],p["flange_radius"],3)
                self.cylinder("drum_"+b,f"collar_{b}_{s}",[cx+s*23,0,z],23,4)
            det=g.detent_disc(count)
            self.prisms("drum_"+b,"detent_"+b,flat_outer(det,-1.5),3,[sign*p["detent_plane_x"],0,z])
            roller_z=z-g.detent_roller_center_radius(count)
            self.cylinder("roller_"+b,"roller_external_"+b,[sign*p["detent_plane_x"],0,roller_z],2,4)
            arm_leaf=next(leaf for leaf,_ in self.parts["arm_"+b] if leaf.label=="DE"+b+"_pivot_arm")
            bounds=arm_leaf.shape().bounding_box();mid=(bounds.min+bounds.max)*.5
            self.box("arm_"+b,"arm_external_"+b,[mid.X,mid.Y,mid.Z],[bounds.size.X,bounds.size.Y,bounds.size.Z])
            sx=sign*(p["detent_plane_x"]+3.1);top_z=(roller_z-3+roller_z)/2-4
            down=[sx,2,18];up=[sx,2,top_z]
            ET.SubElement(self.world,"site",name="spring_base_"+b,pos=fmt(np.asarray(down)*.001),size=".0005",rgba=".8 .6 .2 1",group="2")
            ET.SubElement(self.nodes["arm_"+b],"site",name="spring_tip_"+b,pos=fmt((np.asarray(up)-self.origins["arm_"+b])*.001),size=".0005",rgba=".8 .6 .2 1",group="2")
            self.spring_sites.append({"branch":b,"base":"spring_base_"+b,"tip":"spring_tip_"+b,"body":"arm_"+b,"stiffness_N_m":100,"damping_N_s_m":.02,"free_length_m":(top_z-18)*.001+.001,"max_force_N":2})
        tendons=ET.SubElement(self.root,"tendon")
        for site in self.spring_sites:
            td=ET.SubElement(tendons,"spatial",name="compression_spring_"+site["branch"],width=".0005",rgba=".8 .6 .2 1")
            ET.SubElement(td,"site",site=site["base"]);ET.SubElement(td,"site",site=site["tip"])

    def flap_geometries(self):
        if self.scope=="clutch":return
        path=self.assets_dir/"flap_blank.stl"
        bd.export_stl(g.flap_blank(),str(path),tolerance=.01,angular_tolerance=.1)
        ET.SubElement(self.asset,"mesh",name="flap_blank",file=path.name,scale=".001 .001 .001",maxhullvert="8")
        p=self.p
        for b,n in (("M",60),("H",24)):
            for k in range(n):
                body=f"F{b}_{k:02}"
                ET.SubElement(self.nodes[body],"geom",name="v_"+body,type="mesh",mesh="flap_blank",group="2",rgba=".025 .04 .06 1",contype="0",conaffinity="0")
                self.geom(body,body+"_plate","box",[0,0,p["flap_length"]/2],[p["flap_width"]/2,p["flap_thickness"]/2,p["flap_length"]/2])
                self.geom(body,body+"_barrel","cylinder",[0,0,0],[p["flap_barrel_radius"],p["flap_width"]/2],quat=[math.sqrt(.5),0,math.sqrt(.5),0])
                for face_id,(value,upper) in enumerate(((k,True),((k+1)%n,False))):
                    ink=g.ink_half(value,upper)
                    for j,solid in enumerate(ink.solids()):
                        box=solid.bounding_box();center=(box.min+box.max)*.5
                        self.geom(body,f"{body}_ink_{face_id}_{j}","box",[center.X,center.Y,center.Z],[box.size.X/2,box.size.Y/2,box.size.Z/2],rgba=[.95,.93,.86,1],group=0)

    def frame_collisions(self):
        if self.scope=="clutch":return
        p=self.p;z=p["axis_height"];y=p["input_axis_y"]
        self.box("world","base_external",[-12,-34,3],[312,280,6])
        for sign in (-1,1):
            xx=sign*p["frame_x"]
            for yy in (0,y):self.box("world",f"support_{sign}_{yy}",[xx,yy,(z+12)/2],[6,27,z-12])
            self.box("world",f"support_foot_{sign}",[xx,y/2,9],[18,160,6])
            self.box("world",f"support_beam_{sign}",[xx,y/2,z],[6,abs(y),16])
        self.box("world","center_support",[0,0,(z+6)/2],[22,25,z-6])
        for label_prefix in ("GM_","GH_","A12_"):
            for leaf,path in self.parts["world"]:
                if leaf.label.startswith(label_prefix):
                    # These stationary pieces are axially/radially clear of the
                    # studied moving parts. Bboxes do not replace working teeth.
                    shape=leaf.shape();box=shape.bounding_box();c=(box.min+box.max)*.5
                    self.box("world","fixed_"+leaf.label,[c.X,c.Y,c.Z],[box.size.X,box.size.Y,box.size.Z])
        for b in ("M","H"):
            sign=g.branch_sign(b);count=60 if b=="M" else 24
            # Three native rail stock features, not the bbox of their union.
            # Its wide mounting foot must not fill the empty space up to z=115.
            self.box("world","release_rail_"+b,[sign*12,64,z+20],[3,60,14])
            self.box("world","release_rail_post_"+b,[sign*12,89,(z+32)/2],[3,6,z+8])
            self.box("world","release_rail_foot_"+b,[sign*12,89,9],[16,20,6])
            self.box("world","release_finger_"+b,[sign*20.5,82,z+20],[14,8,12])
            self.box("world","encoder_post_"+b,[sign*122,0,(z+24)/2],[3,24,z+12])
            self.box("world","encoder_foot_"+b,[sign*122,0,9],[28,32,6])
            pivot_z=z-g.detent_roller_center_radius(count)-3
            xx=sign*p["detent_plane_x"]
            self.box("world","detent_post_"+b,[xx,-18,(pivot_z+6)/2],[4,10,pivot_z-6])
            self.cylinder("world","detent_pivot_boss_"+b,[xx,-18,pivot_z],4,4)
            self.box("world","detent_foot_"+b,[sign*(p["detent_plane_x"]-4),-18,9],[13.6,28,6])
            self.box("world","detent_ledge_"+b,[sign*(p["detent_plane_x"]+2),-8,15],[12,30,4])

    def finish(self):
        self.collect();self.build_bodies()
        for body in self.bodies:
            if body.startswith("F"):
                b=body[1];k=int(body[3:]);n=60 if b=="M" else 24
                self.inertia(body,rx(-360*k/n-90))
            else:self.inertia(body)
        self.visuals();self.mechanics();self.flap_geometries();self.frame_collisions()
        actuator=ET.SubElement(self.root,"actuator")
        ET.SubElement(actuator,"general",name="input_request_positive_M_negative_H",joint="I",gaintype="user",biastype="none",ctrlrange="-1 1",forcerange="-.025 .025")
        ET.indent(self.root,space="  ")
        file=self.out/"model.xml";ET.ElementTree(self.root).write(file,encoding="utf-8",xml_declaration=True)
        manifest={"schema_version":1,"scope":self.scope,"engine":"MuJoCo","version":"3.3.7","units":"SI","mm_to_m":.001,
            "cad_sha256":hashlib.sha256((ROOT/"STEP"/"assembly.step").read_bytes()).hexdigest(),
            "cad_document_hash":self.scene.document_hash,"geometry_source_sha256":hashlib.sha256((ROOT/"src"/"geometry.py").read_bytes()).hexdigest(),
            "parameters_sha256":hashlib.sha256((ROOT/"config"/"parameters.yaml").read_bytes()).hexdigest(),
            "xml_sha256":hashlib.sha256(file.read_bytes()).hexdigest(),"bodies":self.bodies,"collision_geoms":self.registry,
            "profiles":self.profile_reports,"compression_springs":self.spring_sites,
            "motor":{"stall_torque_Nm":.025,"no_load_speed_rad_s":3,"reflected_armature_kg_m2":.0001,"status":"proposal_not_calibrated"},
            "assumptions":["Exact CAD solid masses with proposed density, not measured print mass.",
                "Bearings use revolute joints; internal shafts, trunnions and fasteners are visual/mass only.",
                "Flap-barrel external cylinders retain real outer surfaces; joint/pin interiors are not studied.",
                "Nonworking screw/lightening holes are filled in collision proxies; working ratchet voids are preserved.",
                "Stationary frame proxies fill bearing/tool holes whose internals are replaced by joints.",
                "Metal springs use proposed force equivalents; compression spring dynamic mass is neglected.",
                "Release fingers retain CAD retracted inspection positions; no stable HH:MM display is claimed.",
                "Covers/guards may be hidden for inspection; their collision geometry remains enabled.",
                "Parent-child collision filter disabled; no ideal gear or clutch constraints; only input is actuated."],
            "physics_verified":False,"hardware_verified":False,"manufacturing_ready":False}
        (self.out/"manifest.json").write_text(json.dumps(manifest,indent=2),encoding="utf-8")
        print(f"Exported {len(self.bodies)} moving bodies, {len(self.registry)} collision geoms: {file}",flush=True)
        from compact_model import compact_model
        compact_model(self.out)
        from scene_options import refresh_options
        refresh_options(self.out)
        return file


def build_model(scope="full"):
    return Exporter(scope).finish()


if __name__=="__main__":build_model(sys.argv[1] if len(sys.argv)>1 else "full")
