from cadgen import step
import geometry as g


@step(out="../STEP/clutch_test_rig.step", mesh_tolerance=0.01)
def clutch_test_rig():
    return g.clutch_rig()


if __name__ == "__main__":
    clutch_test_rig()
