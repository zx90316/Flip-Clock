"""Create the explicitly new FC-R1 parameter records and model entrypoints."""
from __future__ import annotations
import json
from pathlib import Path

ROOT=Path(__file__).resolve().parents[1]


def record(value,unit,status="proposal",source="FC-R1_new_design_2026-11-04"):
    return {"value":value,"unit":unit,"status":status,"source":source,
            "uncertainty":None,"measured_at":None}


def write_json(path,data):
    path.parent.mkdir(parents=True,exist_ok=True)
    path.write_text(json.dumps(data,ensure_ascii=False,indent=2)+"\n",encoding="utf-8")


def initialize():
    dimensions={
        "hour_flaps":(24,"count"),"minute_flaps":(60,"count"),
        "hour_step":(15,"deg"),"minute_step":(6,"deg"),
        "motor_count":(1,"count"),"shift_actuator_count":(0,"count"),
        "axis_height":(88,"mm"),"input_axis_y":(-108,"mm"),
        "frame_x":(99,"mm"),"gear_plane_x":(76,"mm"),"drum_center_x":(42,"mm"),
        "gear_module":(1.8,"mm"),"gear_width":(6,"mm"),"gear_backlash":(.22,"mm"),
        "pressure_angle":(20,"deg"),"minute_driver_teeth":(40,"count"),
        "minute_idler_teeth":(20,"count"),"minute_output_teeth":(40,"count"),
        "hour_driver_teeth":(60,"count"),"hour_output_teeth":(60,"count"),
        "ratchet_teeth":(36,"count"),"ratchet_tip_radius":(22,"mm"),
        "ratchet_root_radius":(23.4,"mm"),"ratchet_fillet":(.12,"mm"),
        "pawl_width":(2.4,"mm"),"flap_pivot_radius":(48,"mm"),
        "flange_radius":(51,"mm"),"flap_width":(48,"mm"),
        "flap_length":(26,"mm"),"flap_thickness":(.95,"mm"),
        "flap_barrel_radius":(2,"mm"),"flap_pin_bore":(2.3,"mm"),
        "flap_pin_diameter":(2,"mm"),"detent_radius":(45,"mm"),
        "detent_depth":(.9,"mm"),"detent_plane_x":(87,"mm"),"mesh_chord_tolerance":(.01,"mm"),
        "hand_torque_limit":(.15,"N*m")}
    required={"hour_flaps","minute_flaps","hour_step","minute_step","motor_count","shift_actuator_count"}
    config={"schema_version":1,"design_id":"FC-R1", "design_state":"concept_only",
        "supersedes_original_adaptation":True,
        "authority":"user_2026-11-04_full_redesign",
        "coordinates":{"X":"parallel rotating axles","Y":"display front","Z":"up"},
        "parameters":{k:record(v,u,"requirement" if k in required else "proposal",
                              "user_2026-11-04" if k in required else "FC-R1_new_design_2026-11-04")
                      for k,(v,u) in dimensions.items()},
        "verification":{"geometry_verified":False,"physics_verified":False,
                        "motor_model_calibrated":False,"hardware_verified":False,
                        "endurance_verified":False,"manufacturing_ready":False}}
    write_json(ROOT/"config"/"parameters.yaml",config)
    write_json(ROOT/"config"/"interfaces.yaml",{
        "schema_version":1,"original_model_interfaces_used":False,
        "original_compatibility_required":False,"new_geometry_units":"mm",
        "purchased_interfaces":{
            "motor_mount":record(None,"mm","unverified","actual_28BYJ48_measurement_required"),
            "motor_shaft_flat":record(None,"mm","unverified","actual_28BYJ48_measurement_required"),
            "608_bearing_envelope":record([8,22,7],"mm","catalog_nominal","https://api.step.parts/v1/parts/bearing_608zz"),
            "encoder_module_holes":record(None,"mm","unverified","module_not_selected"),
            "encoder_air_gap":record(None,"mm","unverified","encoder_datasheet_and_calibration_required")}})
    write_json(ROOT/"config"/"materials.yaml",{
        "schema_version":1,"all_properties_provisional":True,
        "densities_kg_m3":{"printed_PETG_solid":1270,"printed_PLA_solid":1240,"printed_TPU_solid":1200,"steel":7850,"POM":1410,"pcb_envelope":1800},
        "printed_mass_rule":"CAD full-solid estimate; infill, actual mass and anisotropy unmeasured",
        "friction_coefficient":record(None,"1","unverified","coupon_measurement_required"),
        "pawl_spring_stiffness":record(None,"N*m/rad","unverified","spring_selection_required"),
        "detent_spring_stiffness":record(None,"N/mm","unverified","spring_selection_required")})
    write_json(ROOT/"config"/"motor.yaml",{"candidate":"28BYJ-48 5V + ULN2003", "count":1,
        "geometry":"generic purchased-component envelope only",
        "torque_curve":record(None,"N*m","unverified","bench_measurement_required"),
        "actual_gear_ratio":record(None,"1","unverified","bench_measurement_required"),
        "reversal_backlash":record(None,"deg","unverified","bench_measurement_required")})
    write_json(ROOT/"config"/"simulation.yaml",{"engine":None,"status":"NOT_RUN","units":"SI",
        "gravity_m_s2":[0,0,-9.81],"mm_to_m":.001,
        "forbidden":["output_angle_prescription","ideal_direction_switched_clutch","slot_snapping","ignored_working_contacts"],
        "cad_inspection_pose":"radial_flaps_not_gravity_equilibrium",
        "motor_torque_calibrated":False,"full_contact_model_implemented":False})
    entries={"frame":"frame()","input_drive":"input_drive()",
             "clutch_minute":"clutch_group('M')","clutch_hour":"clutch_group('H')",
             "transmission_minute":"transmission('M')","transmission_hour":"transmission('H')",
             "drum_minute":"drum('M')","drum_hour24":"drum('H')",
             "detent_minute":"detent('M')","detent_hour":"detent('H')",
             "sensors":"sensors()","guards":"guards()",
             "coupon_plate":"coupon_plate()","clutch_test_rig":"clutch_rig()"}
    for name,expression in entries.items():
        code=(f'from cadgen import step\nimport geometry as g\n\n\n'
              f'@step(out="../STEP/{name}.step", mesh_tolerance=0.01)\n'
              f'def {name}():\n    return g.{expression}\n\n\n'
              f'if __name__ == "__main__":\n    {name}()\n')
        (ROOT/"src"/f"{name}.py").write_text(code,encoding="utf-8")
    print("Initialized FC-R1: 14 model entrypoints, new dimensions only.")


if __name__=="__main__":
    initialize()
