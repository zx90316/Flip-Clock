from cadgen import step
import geometry as g


@step(out="../STEP/frame.step", mesh_tolerance=0.01)
def frame():
    return g.frame()


if __name__ == "__main__":
    frame()
