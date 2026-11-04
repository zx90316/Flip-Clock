from cadgen import step
import geometry as g


@step(out="../STEP/guards.step", mesh_tolerance=0.01)
def guards():
    return g.guards()


if __name__ == "__main__":
    guards()
