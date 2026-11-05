from cadgen import step
import r2_geometry as g

@step(out="../STEP/assembly.step", mesh_tolerance=.02)
def assembly():
    return g.assembly()

if __name__ == "__main__":
    assembly()
