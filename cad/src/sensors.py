from cadgen import step
import geometry as g


@step(out="../STEP/sensors.step", mesh_tolerance=0.01)
def sensors():
    return g.sensors()


if __name__ == "__main__":
    sensors()
