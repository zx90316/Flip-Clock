from cadgen import step
import geometry as g


@step(out="../STEP/drum_hour24.step", mesh_tolerance=0.01)
def drum_hour24():
    return g.drum('H')


if __name__ == "__main__":
    drum_hour24()
