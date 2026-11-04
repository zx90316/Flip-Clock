"""Nominal dimensions projected from the new saved STEP; no invented fits."""
from pathlib import Path
import math
from cadgen import read_step, build123d as bd
from cadgen.eng_drawing import Sheet, eng_drawing

ROOT=Path(__file__).resolve().parents[1]


def circle_centers(part,radius):
    result={}
    for edge in part.edges():
        if edge.geom_type==bd.GeomType.CIRCLE and abs(edge.radius-radius)<1e-5 and abs(edge.length-2*math.pi*radius)<1e-4:
            c=edge.arc_center
            key=(round(c.X,5),round(c.Y,5))
            if key not in result or c.Z>result[key][2]:result[key]=(c.X,c.Y,c.Z)
    return list(result.values())


@eng_drawing(out="../PDF/critical_parts_drawing.pdf")
def critical_parts_drawing():
    sheets=[]
    for branch,count in (("H",24),("M",60)):
        part=read_step(ROOT/"STEP"/"parts"/f"D{branch}_flange_L.step")
        sheet=Sheet("A3",scale=1,title=f"FC-R1 {branch} DRUM FLANGE - PROTOTYPE",
                    part_number=f"D{branch}-FLANGE",material="PETG - PROPOSAL",revision="P1",
                    author="FC-R1",notes=["CONCEPT ONLY. NOMINAL DIMENSIONS.","FITS AND RELEASE MOTION UNVERIFIED."])
        top,front,right,iso=sheet.three_views(part,iso=True,gap=38)
        top.overall();front.overall()
        pivots=sorted(circle_centers(part,1.15),key=lambda q:math.atan2(q[1],q[0]))
        fixing=sorted(circle_centers(part,1.65))
        bore=circle_centers(part,4.2)
        top.hole(pivots[-1],2.3,thru=True,count=count,angle=45)
        top.hole(fixing[0],3.3,thru=True,count=3,angle=150)
        top.hole(bore[0],8.4,thru=True,angle=225)
        sheets.append(sheet)
    part=read_step(ROOT/"STEP"/"parts"/"CM_pawl.step")
    sheet=Sheet("A4",scale=4,title="FC-R1 PIVOTING PAWL - PROTOTYPE",part_number="CM-PAWL",
                material="PETG - PROPOSAL",revision="P1",author="FC-R1",
                notes=["CONCEPT ONLY. NOMINAL DIMENSIONS.","METAL PIN AND SPRING REQUIRED."])
    top,front,right,iso=sheet.three_views(part,iso=True,gap=30)
    top.overall();front.overall()
    top.hole(circle_centers(part,1.15)[0],2.3,thru=True,angle=135)
    sheets.append(sheet)
    return sheets


if __name__=="__main__":critical_parts_drawing()
