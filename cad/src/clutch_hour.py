from cadgen import step
import geometry as g


@step(out="../STEP/clutch_hour.step", mesh_tolerance=0.01)
def clutch_hour():
    return g.clutch_group('H')


if __name__ == "__main__":
    clutch_hour()
