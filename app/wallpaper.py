"""Approved poster-column wallpaper with bottom-left fade and progressive blur."""
from PIL import Image,ImageDraw,ImageFilter,ImageOps
import math
W,H=2560,1440

def smooth(v):
    v=max(0,min(1,v));return v*v*(3-2*v)

def render_wallpaper(posters,out):
    # Each column keeps the real 2:3 proportions, with a different scale and
    # vertical offset. Larger columns interrupt the regular grid rhythm.
    # Draw well past the visible crop before rotating. This avoids empty
    # triangular corners without removing the intentional black fade.
    pad=800;cropw,croph=3500,1969
    grid=Image.new('RGB',(cropw+pad*2,croph+pad*2),(8,8,8))
    widths=[420,620,510,670,710,520]
    starts=[-300,-423,-570,-536,-242,-201]
    x=pad-50+120;slots=[]
    def column(x,width,start):
        height=width*3//2;y=pad+start
        while y>0:y-=height+24
        while y<grid.height:
            slots.append((x,y,width,height));y+=height+24
    for width,start in zip(widths,starts):
        column(x,width,start)
        x+=width+24
    while x<grid.width:
        column(x,560,-663);x+=584
    x=pad-50+120-584
    while x+560>0:
        column(x,560,-288);x-=584
    # Allocate unique artwork to visible slots before spending any posters on
    # overscan. Test rotated bounds conservatively, including partial edges.
    c=math.cos(math.radians(5));s=math.sin(math.radians(5))
    def visible(slot):
        x,y,width,height=slot;cx,cy=grid.width/2,grid.height/2
        points=[(cx+c*(xx-cx)-s*(yy-cy),cy+s*(xx-cx)+c*(yy-cy))
                for xx,yy in [(x,y),(x+width,y),(x+width,y+height),(x,y+height)]]
        return (max(a for a,b in points)>pad and min(a for a,b in points)<pad+cropw
                and max(b for a,b in points)>pad and min(b for a,b in points)<pad+croph)
    onscreen=[slot for slot in slots if visible(slot)]
    assert len(posters)>=len(onscreen), f'Need {len(onscreen)} distinct posters; have {len(posters)}'
    # Keep existing titles on the same cards while shifting the grid; assign
    # extra titles only to the newly revealed edge cards.
    reference=[slot for slot in slots if visible((slot[0]-120,*slot[1:]))]
    assignments={slot:i for i,slot in enumerate(reference)}
    next_index=len(reference)
    for slot in onscreen:
        if slot not in assignments:
            assignments[slot]=next_index;next_index+=1
    assert len(posters)>=next_index, f'Need {next_index} distinct posters'
    for slot in slots:
        x,y,width,height=slot
        im=ImageOps.fit(posters[assignments.get(slot,0)],(width,height),Image.Resampling.LANCZOS)
        mask=Image.new('L',im.size);ImageDraw.Draw(mask).rounded_rectangle((0,0,width-1,height-1),radius=30,fill=255)
        grid.paste(im,(x,y),mask)
    grid=grid.rotate(-5,Image.Resampling.BICUBIC,expand=False,fillcolor=(8,8,8))
    box=(pad,pad,pad+cropw,pad+croph)
    coverage=Image.new('L',grid.size,255).rotate(-5,expand=False,fillcolor=0).crop(box)
    assert all(coverage.getpixel(p)==255 for p in [(0,0),(cropw-1,0),(0,croph-1),(cropw-1,croph-1)]), 'Rotation exposed a canvas corner'
    wall=grid.crop(box).resize((W,H),Image.Resampling.LANCZOS)
    fade=Image.new('L',(640,360));blur=Image.new('L',fade.size)
    fp=fade.load();bp=blur.load()
    for y in range(360):
        yy=y/359
        for x in range(640):
            xx=x/639
            # Keep the lower-right artwork visible: the deep bottom fade
            # belongs to the left, rather than darkening the whole bottom.
            dark=min(1,.12+.68*(1-xx)**1.6+.76*yy**1.8*(1-.85*xx))
            # A compact, feathered top-right shadow leaves the approved
            # geometry intact and keeps most of the artwork crisp.
            corner=smooth(1-(((1-xx)/.34)**2+(yy/.40)**2)**.5)
            base_blur=.8*smooth((dark-.22)/.65)
            dark=1-(1-dark)*(1-.48*corner)
            fp[x,y]=round(255*dark)
            bp[x,y]=round(255*(1-(1-base_blur)*(1-.60*corner)))
    fade=fade.resize((W,H),Image.Resampling.BICUBIC)
    blur=blur.resize((W,H),Image.Resampling.BICUBIC)
    # Detail softens through the shadow, while the clearer upper-right art
    # remains crisp. The bottom-left reaches true OLED black.
    wall=Image.composite(wall.filter(ImageFilter.GaussianBlur(16)),wall,blur)
    wall=Image.composite(Image.new('RGB',(W,H),'black'),wall,fade)
    wall.save(out,quality=92,method=5)
    return [{'posterIndex':assignments[slot],'position':list(slot)} for slot in onscreen]
