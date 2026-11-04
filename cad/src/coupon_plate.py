from cadgen import step
import geometry as g


@step(out="../STEP/coupon_plate.step", mesh_tolerance=0.01)
def coupon_plate():
    return g.coupon_plate()


if __name__ == "__main__":
    coupon_plate()
