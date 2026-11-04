from cadgen import step
import geometry as g


@step(out="../STEP/drum_minute.step", mesh_tolerance=0.01)
def drum_minute():
    return g.drum('M')


if __name__ == "__main__":
    drum_minute()
