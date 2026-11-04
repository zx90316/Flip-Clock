from cadgen import step
import geometry as g


@step(out="../STEP/detent_minute.step", mesh_tolerance=0.01)
def detent_minute():
    return g.detent('M')


if __name__ == "__main__":
    detent_minute()
