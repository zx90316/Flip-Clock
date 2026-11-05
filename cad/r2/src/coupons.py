from cadgen import step, stl, build123d as bd
import r2_geometry as g

@step(out="../STEP/coupons.step", mesh_tolerance=.01)
@stl(out="../STL/coupons.stl")
def coupons():
    parts = g.coupons()
    leaf = parts.children[0].rotate(bd.Axis.X, -90)
    leaf = bd.Pos(0, 0, -leaf.bounding_box().min.Z) * leaf
    shaft = bd.Pos(19.6, 25, 1.5) * bd.Box(50, 16, 3)
    for i, diameter in enumerate((8.0, 8.1, 8.2, 8.3)):
        shaft -= bd.Pos(2.2 + i * 11.6, 25, 1.5) * bd.Cylinder(diameter / 2, 6)
    return g.group("FC_R2_flat_fit_coupons", [leaf, parts.children[1], g.named(shaft, "CP_8mm_shaft_bore_ladder", "H")])

if __name__ == "__main__":
    coupons()
