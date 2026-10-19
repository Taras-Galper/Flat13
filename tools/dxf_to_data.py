"""
dira.dxf  ->  js/data.js + assets/plan_rooms.png + assets/plan_walldist.png

The DXF is a PDF conversion: one layer, polylines only, units mm, no text.
Walls are recovered from the 45° hatching (poché): regions bounded by orthogonal
lines that are densely filled with diagonal hatch lines are wall. Thin partitions that
are not hatched, rooms, openings and furniture are listed by hand below / in furniture.js.

usage:  python tools/dxf_to_data.py path/to/dira.dxf
needs:  pip install ezdxf opencv-python-headless scipy numpy
"""
import sys, json, os
import numpy as np, cv2, ezdxf
from scipy import ndimage

HERE = os.path.dirname(os.path.abspath(__file__)); ROOT = os.path.dirname(HERE)
dxf = sys.argv[1] if len(sys.argv) > 1 else os.path.join(ROOT, 'dira.dxf')

# ---------------------------------------------------------------- 1. segments in metres
S = []
for e in ezdxf.readfile(dxf).modelspace():
    if e.dxftype() != 'POLYLINE': continue
    p = [(v.dxf.location.x / 1000, v.dxf.location.y / 1000) for v in e.vertices]
    if e.is_closed and p: p.append(p[0])
    S += [(a[0], a[1], b[0], b[1]) for a, b in zip(p[:-1], p[1:])]
S = np.array(S); d = S[:, 2:] - S[:, :2]
ang = np.degrees(np.arctan2(d[:, 1], d[:, 0])) % 180

# ---------------------------------------------------------------- 2. wall mask from hatch density
X0, Y0, R = -8.0, -0.1, 100            # 1 cm raster
W, H = int(16.4 * R), int(14.1 * R)
px = lambda x, y: (int(round((x - X0) * R)), int(round(H - (y - Y0) * R)))
bar = np.zeros((H, W), np.uint8); hat = np.zeros((H, W), np.uint8)
axis = (np.minimum(ang, 180 - ang) < 1) | (abs(ang - 90) < 1)
diag = (abs(ang - 45) < 2) | (abs(ang - 135) < 2)
for s, a, g in zip(S, axis, diag):
    if a: cv2.line(bar, px(s[0], s[1]), px(s[2], s[3]), 255, 1)
    elif g: cv2.line(hat, px(s[0], s[1]), px(s[2], s[3]), 255, 1)
n, lab, st, _ = cv2.connectedComponentsWithStats(255 - bar, connectivity=4)
dens = np.bincount(lab[hat > 0].ravel(), minlength=n) / np.maximum(st[:, 4], 1)
keep = (dens > 0.06) & (st[:, 4] > 20); keep[0] = False
m = cv2.morphologyEx(keep[lab].astype(np.uint8) * 255, cv2.MORPH_CLOSE, np.ones((3, 3), np.uint8))
n, lab, st, _ = cv2.connectedComponentsWithStats(m)
m = np.isin(lab, [i for i in range(1, n) if st[i, 4] > 400]).astype(np.uint8) * 255

# thin partitions drawn without hatch (plan metres x0,x1,y0,y1)
for x0, x1, y0, y1 in [(-1.99, -1.87, 2.95, 4.68), (0.88, 0.98, 2.95, 4.68), (-4.53, -4.43, 5.62, 6.0),
                       (-4.53, -4.43, 4.70, 4.82), (-3.60, -3.47, 2.80, 3.02), (-3.60, -3.47, 4.28, 4.70)]:
    cv2.rectangle(m, px(x0, y1), px(x1, y0), 255, -1)
m[:px(0, 13.4)[1], :] = 0

def conv(c):
    c = cv2.approxPolyDP(c, 1.2, True)[:, 0, :]
    return [[round(X0 + u / R, 3), round(Y0 + (H - v) / R, 3)] for u, v in c]
cs, hier = cv2.findContours(m, cv2.RETR_CCOMP, cv2.CHAIN_APPROX_SIMPLE)
walls = []
for i, c in enumerate(cs):
    if hier[0][i][3] != -1 or cv2.contourArea(c) < 300: continue
    holes, j = [], hier[0][i][2]
    while j != -1:
        if cv2.contourArea(cs[j]) > 40: holes.append(conv(cs[j]))
        j = hier[0][j][0]
    walls.append({'outer': conv(c), 'holes': holes})

# ---------------------------------------------------------------- 3. rooms + openings (read off the drawing)
rooms = [
 dict(id='entry', he='מבואה', en='Entry', rects=[[5.2, 7.77, 4.35, 5.92]], floor='tile'),
 dict(id='living', he='ח.דיור', en='Living room', rects=[[3.49, 7.77, 5.92, 9.25], [3.49, 5.2, 4.05, 5.92]], floor='tile', label=[5.6, 7.7], dims='4.27 × 4.86'),
 dict(id='kitchen', he='מטבח', en='Kitchen', rects=[[2.22, 6.08, 0.39, 4.05], [2.11, 3.49, 4.05, 4.75]], floor='tile', label=[3.9, 2.3], dims='3.81 × 3.66'),
 dict(id='corridor', he='מסדרון', en='Corridor', rects=[[-4.43, 3.49, 4.75, 5.92]], floor='tile'),
 dict(id='wc', he='ש.אורחים', en='Guest WC', rects=[[0.98, 2.11, 2.95, 4.65]], floor='tile_small', label=[1.55, 4.15], dims='1.07 × 1.68'),
 dict(id='bath', he='ח.רחצה כללי', en='Bathroom', rects=[[-1.87, 0.88, 2.95, 4.67]], floor='tile_small', label=[-0.45, 4.15], dims='2.70 × 1.68'),
 dict(id='laundry', he='ח.שירות', en='Laundry', rects=[[-3.47, -1.99, 2.95, 4.67]], floor='tile_small', label=[-2.73, 4.2], dims='1.45 × 1.68'),
 dict(id='service', he='משטח מונמך', en='Service balcony', rects=[[-7.79, -3.6, 2.65, 4.4]], floor='concrete', label=[-5.7, 3.6]),
 dict(id='bed4', he='ח.שינה', en='Bedroom 4', rects=[[-7.34, -4.53, 4.73, 8.02]], floor='oak', label=[-5.85, 6.55], dims='2.75 × 3.20', num=4),
 dict(id='passage', he='', en='', rects=[[-4.43, -2.85, 5.92, 9.53], [-4.17, -2.85, 8.02, 9.53]], floor='oak'),
 dict(id='master', he='ח.שינה הורים', en='Main bedroom', rects=[[-7.34, -4.17, 8.12, 11.31]], floor='oak', label=[-5.7, 8.95], dims='3.12 × 3.15', num=1),
 dict(id='ensuite', he='ח.רחצה הורים', en='En-suite', rects=[[-4.07, -2.19, 9.73, 11.31]], floor='tile_small', label=[-3.3, 10.15], dims='1.83 × 1.65'),
 dict(id='mamad', he='ממ"ד / ח.שינה', en='Safe room · Bedroom 2', rects=[[-2.6, 0.32, 6.16, 9.33]], floor='oak', label=[-1.05, 7.45], dims='2.84 × 3.09', num=2),
 dict(id='bed3', he='ח.שינה', en='Bedroom 3', rects=[[0.56, 3.39, 6.01, 9.25]], floor='oak', label=[1.6, 7.45], dims='2.75 × 3.20', num=3),
 dict(id='terrace', he='מרפסת', en='Balcony', rects=[[-1.73, 7.80, 9.70, 12.98]], floor='deck', label=[3.0, 11.4], dims='9.50 × 3.30'),
 dict(id='landing', he='לובי קומתי', en='Lift lobby', rects=[[6.40, 10.40, 0.90, 4.10]], floor='tile', label=[8.6, 2.2]),
]
O = []
def win(r, sill, head, room, kind='window'): O.append(dict(kind=kind, rect=r, sill=sill, head=head, room=room))
def door(r, hinge, swing, room, kind='door'): O.append(dict(kind=kind, rect=r, sill=0, head=2.1, hinge=hinge, swing=swing, room=room))
win([-7.79, -7.34, 9.11, 10.52], 0.9, 2.2, 'master'); win([-7.79, -7.34, 5.56, 6.76], 0.9, 2.2, 'bed4')
win([-6.40, -5.00, 11.31, 11.76], 0.9, 2.2, 'master'); win([-3.69, -3.18, 11.31, 11.76], 1.4, 2.2, 'ensuite')
win([-1.31, -0.27, 9.33, 9.70], 0.9, 2.1, 'mamad'); win([1.29, 2.50, 9.25, 9.70], 0.9, 2.2, 'bed3')
win([4.41, 7.42, 9.25, 9.70], 0.0, 2.4, 'living', 'slider'); win([1.77, 2.22, 1.05, 2.32], 1.0, 2.2, 'kitchen')
win([-3.60, -3.47, 3.02, 4.28], 0.0, 2.1, 'laundry', 'glassdoor')
door([6.64, 7.66, 4.10, 4.35], [7.62, 4.33], [0, 1], 'entry', 'entry')
door([0.56, 1.48, 5.92, 6.01], [0.60, 5.99], [0, 1], 'bed3'); door([-0.64, 0.15, 5.89, 6.16], [0.13, 5.92], [0, -1], 'mamad')
door([-4.43, -3.59, 5.92, 6.02], [-4.40, 5.99], [0, 1], 'passage'); door([-4.53, -4.43, 4.82, 5.62], [-4.45, 4.85], [-1, 0], 'bed4')
door([-4.17, -4.07, 9.73, 10.37], [-4.09, 9.76], [1, 0], 'ensuite'); door([-2.82, -2.08, 4.67, 4.76], [-2.11, 4.69], [0, -1], 'laundry')
door([-0.82, -0.05, 4.67, 4.76], [-0.79, 4.69], [0, -1], 'bath'); door([1.09, 1.76, 4.65, 4.75], [1.12, 4.67], [0, -1], 'wc')

# ---------------------------------------------------------------- 4. shader textures: room ids + distance to walls
BX0, BX1, BY0, BY1, RES = -8.5, 11.0, -0.5, 14.5, 25    # 4 cm
w, h = int((BX1 - BX0) * RES), int((BY1 - BY0) * RES)
ids = np.zeros((h, w), np.uint8)
for i, r in enumerate(rooms):
    for x0, x1, y0, y1 in r['rects']:
        ids[int((BY1 - y1) * RES):int(np.ceil((BY1 - y0) * RES)), int((x0 - BX0) * RES):int(np.ceil((x1 - BX0) * RES))] = i + 1
dd, ind = ndimage.distance_transform_edt(ids == 0, return_indices=True)
ids = np.where(dd < 6, ids[ind[0], ind[1]], ids)
cv2.imwrite(os.path.join(ROOT, 'assets/plan_rooms.png'), ids)
xs = BX0 + (np.arange(w) + .5) / RES; ys = BY1 - (np.arange(h) + .5) / RES
cx = ((xs - X0) * R).astype(int); cy = (H - (ys - Y0) * R).astype(int)
vx = (cx >= 0) & (cx < W); vy = (cy >= 0) & (cy < H)
sub = np.zeros((h, w), np.uint8); sub[np.ix_(vy, vx)] = m[np.ix_(cy[vy], cx[vx])]
dist = ndimage.distance_transform_edt(sub == 0) / RES
cv2.imwrite(os.path.join(ROOT, 'assets/plan_walldist.png'), np.clip(dist / 1.2 * 255, 0, 255).astype(np.uint8))
fm = cv2.morphologyEx((((ids > 0) | (sub > 0)) * 255).astype(np.uint8), cv2.MORPH_CLOSE, np.ones((5, 5), np.uint8))
cs, _ = cv2.findContours(fm, cv2.RETR_EXTERNAL, cv2.CHAIN_APPROX_SIMPLE)
slabs = [[[round(BX0 + u / RES, 3), round(BY1 - v / RES, 3)] for u, v in cv2.approxPolyDP(c, 1.0, True)[:, 0, :]] for c in cs if cv2.contourArea(c) > 200]

data = dict(walls=walls, rooms=rooms, openings=O, slabs=slabs, grid=dict(x0=BX0, x1=BX1, y0=BY0, y1=BY1, w=w, h=h))
open(os.path.join(ROOT, 'js/data.js'), 'w', encoding='utf-8').write(
    '// Generated by tools/dxf_to_data.py from dira.dxf (plan metres: x east on the sheet, y up the sheet)\nexport const DATA = ' + json.dumps(data, ensure_ascii=False) + ';\n')
print(f'{len(walls)} wall solids, {len(rooms)} rooms, {len(O)} openings')
