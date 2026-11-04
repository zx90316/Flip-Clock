from cadgen import step
import geometry as g


@step(out="../STEP/detent_hour.step", mesh_tolerance=0.01)
def detent_hour():
    return g.detent('H')


if __name__ == "__main__":
    detent_hour()
