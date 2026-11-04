from cadgen import build123d as bd, step
from settings import values
from geometry import place_axial, group, fasteners
from frame import frame
from input_drive import input_drive
from clutch_minute import clutch_minute
from clutch_hour import clutch_hour
from transmission_minute import transmission_minute
from transmission_hour import transmission_hour
from drum_minute import drum_minute
from drum_hour24 import drum_hour24
from detent_minute import detent_minute
from detent_hour import detent_hour
from sensors import sensors
from guards import guards


@step(out="../STEP/assembly.step",mesh_tolerance=0.01)
def assembly():
    p=values()
    return group("FC_R1_New_Design_CONCEPT_ONLY",[
        frame(), input_drive(),
        place_axial(clutch_minute(),-p["gear_plane_x"],p["input_axis_y"],p["axis_height"]),
        place_axial(clutch_hour(),p["gear_plane_x"],p["input_axis_y"],p["axis_height"]),
        transmission_minute(),transmission_hour(),drum_minute(),drum_hour24(),
        detent_minute(),detent_hour(),sensors(),guards(),fasteners()])


if __name__=="__main__":
    assembly()
