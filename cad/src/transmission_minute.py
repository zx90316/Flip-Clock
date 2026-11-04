from cadgen import step
import geometry as g


@step(out="../STEP/transmission_minute.step", mesh_tolerance=0.01)
def transmission_minute():
    return g.transmission('M')


if __name__ == "__main__":
    transmission_minute()
