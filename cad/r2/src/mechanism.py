from cadgen import step
import r2_geometry as g

@step(out="../STEP/mechanism.step", mesh_tolerance=.02)
def mechanism():
    return g.mechanism()

if __name__ == "__main__":
    mechanism()
