"""Render solver-recorded states, never use rendered poses as physics evidence."""
from __future__ import annotations
import json
import gzip
import hashlib
from pathlib import Path
import time
import numpy as np
import mujoco as mj
import imageio.v2 as imageio
from PIL import Image,ImageDraw,ImageFont
from dynamics import load_model,contact_settings,solver_settings

ROOT=Path(__file__).resolve().parents[1]


def font(size):
    for path in (Path("C:/Windows/Fonts/msjh.ttc"),Path("C:/Windows/Fonts/arial.ttf")):
        if path.exists():return ImageFont.truetype(str(path),size)
    return ImageFont.load_default(size=size)


def camera(kind="overview"):
    cam=mj.MjvCamera();mj.mjv_defaultCamera(cam)
    if kind=="overview":
        cam.lookat[:]=[0,-.035,.075];cam.distance=.49;cam.azimuth=-70;cam.elevation=-23
    elif kind=="front":
        cam.lookat[:]=[0,0,.085];cam.distance=.31;cam.azimuth=-90;cam.elevation=-10
    else:
        cam.lookat[:]=[0,-.065,.085];cam.distance=.39;cam.azimuth=95;cam.elevation=-30
    return cam


def contact_overlay(frame,scene,points):
    """Project real contact points; draw through occluders for inspection."""
    cams=[scene.camera[0],scene.camera[1]]
    position=np.mean([c.pos for c in cams],axis=0)
    forward=np.mean([c.forward for c in cams],axis=0);forward/=np.linalg.norm(forward)
    up=np.mean([c.up for c in cams],axis=0);up/=np.linalg.norm(up)
    right=np.cross(forward,up);right/=np.linalg.norm(right)
    top=float(cams[0].frustum_top);bottom=float(cams[0].frustum_bottom);near=float(cams[0].frustum_near)
    height=top-bottom;width=height*frame.width/frame.height;center=float(cams[0].frustum_center)
    draw=ImageDraw.Draw(frame,"RGBA")
    for point in points:
        delta=np.asarray(point[:3])-position;depth=float(delta@forward)
        if depth<=near:continue
        xx=(.5+(near*float(delta@right)/depth-center)/width)*frame.width
        yy=(top-near*float(delta@up)/depth)/height*frame.height
        if 0<xx<frame.width and 97<yy<646:draw.ellipse([xx-2.2,yy-2.2,xx+2.2,yy+2.2],fill=(255,49,42,225),outline=(255,218,207,230),width=1)


def render_run(run):
    run=run.resolve();config=json.loads((run/"run_config.json").read_text(encoding="utf-8"));summary=json.loads((run/"summary.json").read_text(encoding="utf-8"))
    states=np.load(run/"states.npz",allow_pickle=False)
    with gzip.open(run/"contact_points.json.gz","rt",encoding="utf-8") as stream:contact_points=json.load(stream)
    m,d,dynamics,manifest=load_model(run/"model");m.opt.timestep=config["timestep_s"];m.opt.gravity[:]=config["gravity_m_s2"]
    if isinstance(config.get("contact_model"),dict):contact_settings(m,config["contact_model"]["solref"][0])
    if isinstance(config.get("solver"),dict):solver_settings(m,config["solver"]["algorithm"],config["solver"]["iterations"])
    opt=mj.MjvOption();mj.mjv_defaultOption(opt);opt.geomgroup[:]=[1,1,1,0,0,0]
    opt.flags[mj.mjtVisFlag.mjVIS_CONTACTPOINT]=False
    opt.flags[mj.mjtVisFlag.mjVIS_CONTACTFORCE]=False
    title_font=font(27);text_font=font(20);small_font=font(17)
    labels={"overview":"整機：重力與接觸碰撞","front":"翻片近看：84 片獨立剛體","rear":"背面：棘爪、齒輪與定位輪"}
    started=time.perf_counter();rendered=0
    with mj.Renderer(m,height=720,width=1280,max_geom=20000) as renderer:
        for kind in ("overview","front","rear"):
            target=run/("physics.mp4" if kind=="overview" else kind+".mp4")
            with imageio.get_writer(str(target),fps=30,codec="libx264",quality=8,macro_block_size=16,ffmpeg_log_level="error",output_params=["-movflags","+faststart","-pix_fmt","yuv420p"]) as video:
                last=None
                for i,t in enumerate(states["time"]):
                    # This is replay of recorded engine output, not an integration
                    # loop or a claim that imposed angles establish performance.
                    d.qpos[:]=states["qpos"][i];d.qvel[:]=states["qvel"][i];d.time=float(t)
                    from runner import request_at
                    d.ctrl[0]=np.clip(request_at(config["case"],float(t),config["requested_duration_s"])*config["torque_scale"],-1,1)
                    mj.mj_forward(m,d)
                    renderer.update_scene(d,camera=camera(kind),scene_option=opt)
                    # Actual logged contact locations, with enlarged red markers
                    # for legibility. Marker radius is not collision margin.
                    for point in contact_points[i]:
                        if renderer.scene.ngeom>=renderer.scene.maxgeom:break
                        geom=renderer.scene.geoms[renderer.scene.ngeom]
                        mj.mjv_initGeom(geom,mj.mjtGeom.mjGEOM_SPHERE,np.array([.00045]*3),np.array(point[:3]),np.eye(3).reshape(-1),np.array([1.,.10,.08,1.]))
                        renderer.scene.ngeom+=1
                    frame=Image.fromarray(renderer.render());contact_overlay(frame,renderer.scene,contact_points[i]);draw=ImageDraw.Draw(frame,"RGBA")
                    draw.rectangle([0,0,1280,96],fill=(17,28,39,238));draw.rectangle([0,646,1280,720],fill=(17,28,39,238))
                    draw.text((24,12),"FC-R1  "+labels[kind],font=title_font,fill="white")
                    draw.text((24,53),f"MuJoCo {config['version']} ｜ g = {abs(config['gravity_m_s2'][2]):.2f} m/s² ｜ t = {t:.3f} s ｜ 0.25 倍慢速",font=text_font,fill=(169,219,226,255))
                    motor="重力落片／輸入力矩為 0" if abs(d.ctrl[0])<.001 else ("正向輸入" if d.ctrl[0]>0 else "反向輸入")+f" ｜ 馬達力矩 {float(d.actuator_force[0]):+.5f} N·m"
                    draw.text((24,656),motor+f" ｜ 接觸點 {int(states['ncon'][i])}",font=text_font,fill="white")
                    draw.text((24,687),"紅點：接觸位置（穿透顯示）。彈簧、摩擦與馬達尚未實測校準；放行指仍退回。",font=small_font,fill=(224,194,143,255))
                    arr=np.asarray(frame);last=arr
                    if i==0:
                        for _ in range(25):video.append_data(arr)
                        if kind=="overview":frame.save(run/"initial.png")
                    video.append_data(arr);rendered+=1
                    if i in (len(states["time"])//3,len(states["time"])//2,len(states["time"])-1):frame.save(run/(kind+f"_{i:03}.png"))
                    if kind=="overview" and i==len(states["time"])//2:frame.save(run/"poster.png")
                    if i%60==0:print(json.dumps({"render":kind,"frame":i,"of":len(states["time"]),"wall_s":round(time.perf_counter()-started,1)}),flush=True)
                for _ in range(35):video.append_data(last)
            print("VIDEO "+str(target),flush=True)
    report={"source":"Recorded MuJoCo solver qpos/qvel, states.npz","rendered_frames":rendered,"replay_speed":.25,"views":["physics.mp4","front.mp4","rear.mp4"],"wall_seconds":time.perf_counter()-started,"physics_verified":False,
        "render_code_sha256":hashlib.sha256(Path(__file__).read_bytes()).hexdigest(),"contact_markers":"Logged solver contact positions; 2D x-ray markers show occluded contacts. Marker size is not collision margin."}
    (run/"render.json").write_text(json.dumps(report,indent=2),encoding="utf-8")
    return 0

