from cadgen import step
import geometry as g


@step(out="../STEP/transmission_hour.step", mesh_tolerance=0.01)
def transmission_hour():
    return g.transmission('H')


if __name__ == "__main__":
    transmission_hour()
