from pathlib import Path
from PIL import Image,ImageOps,ImageDraw,ImageFont

ROOT=Path(__file__).resolve().parents[1]
folder=ROOT/"tmp"/"review"
names=["assembly","assembly_rear","assembly_side","frame","input_drive","transmission_minute",
       "transmission_hour","drum_minute","drum_hour24","detent_minute","detent_hour","sensors",
       "guards","clutch_minute","clutch_hour","clutch_test_rig","coupon_plate"]
font=ImageFont.load_default(size=20)
for page in range(2):
    section=names[page*9:(page+1)*9]
    canvas=Image.new("RGB",(1800,1440),"#FFFFFF")
    draw=ImageDraw.Draw(canvas)
    for index,name in enumerate(section):
        pic=Image.open(folder/(name+".png")).convert("RGB")
        pic=ImageOps.contain(pic,(594,428))
        x=(index%3)*600+(600-pic.width)//2;y=(index//3)*480+34
        canvas.paste(pic,(x,y));draw.text(((index%3)*600+12,(index//3)*480+6),name,fill="#14202C",font=font)
    path=folder/f"contact_sheet_{page+1}.png"
    canvas.save(path)
    print(path)
