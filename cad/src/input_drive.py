from cadgen import step
import geometry as g


@step(out="../STEP/input_drive.step", mesh_tolerance=0.01)
def input_drive():
    return g.input_drive()


if __name__ == "__main__":
    input_drive()
