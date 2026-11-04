from cadgen import step
import geometry as g


@step(out="../STEP/clutch_minute.step", mesh_tolerance=0.01)
def clutch_minute():
    return g.clutch_group('M')


if __name__ == "__main__":
    clutch_minute()
