import ezdxf
from math import tan, radians, cos, pi, sqrt
import random
import time
import cadquery as cq
from cadquery import exporters
import python_minifier
import os

VIEW_GAP = 30
AXIS_OVERHANG = 5.0

def hex_vertices(cx, cy, R_circ):
    from math import sin
    verts = []
    for i in range(6):
        angle = radians(90 + 60 * i)
        verts.append((cx + R_circ * cos(angle),
                      cy + R_circ * sin(angle)))
    return verts

def create_doc_and_layers():
    doc = ezdxf.new('R2010', setup=True, units=4)
    msp = doc.modelspace()
    doc.layers.add(name='Main',    color=7,
                   linetype='CONTINUOUS', lineweight=50)
    doc.layers.add(name='Thread',  color=4,
                   linetype='CONTINUOUS', lineweight=25)
    doc.layers.add(name='Hatches', color=8,
                   linetype='CONTINUOUS', lineweight=25)
    doc.layers.add(name='Axises',  color=6, linetype='CENTER')
    doc.layers.add(name='Measure', color=170, lineweight=25)
    return doc, msp

def draw_shank(msp, D, L, CHAMFER_TIP, L_SHANK):
    # Ось болта
    msp.add_line((-AXIS_OVERHANG, 0),
                 (L + AXIS_OVERHANG, 0),
                 dxfattribs={'layer': 'Axises'})

    # Верхняя боковая поверхность стержня
    shank_top_start = (L_SHANK, D / 2)
    shank_chamfer_x = L - CHAMFER_TIP
    shank_top_end   = (shank_chamfer_x, D / 2)
    line_top = msp.add_line(shank_top_start, shank_top_end,
                            dxfattribs={'layer': 'Main'})
    # Фаска 45 на торце
    chamfer_start = shank_top_end
    chamfer_end   = (L, D / 2 - CHAMFER_TIP)
    line_ch = msp.add_line(chamfer_start, chamfer_end,
                           dxfattribs={'layer': 'Main'})
    # Торцевая вертикаль
    line_tip = msp.add_line(chamfer_end, (L, 0),
                            dxfattribs={'layer': 'Main'})
    # Симметрия — отражение вниз
    for ln in [line_top, line_ch, line_tip]:
        sym = ln.copy()
        msp.add_entity(sym)
        sym.scale(1, -1, 1)
    return chamfer_start, chamfer_end

def draw_head(msp, D, L, L_SHANK, R_inscribed, R_circ,
              HEAD_CHAMFER_DEG):
    head_chamfer_dy = R_circ - R_inscribed
    head_chamfer_dx = tan(radians(HEAD_CHAMFER_DEG)) * head_chamfer_dy
    head_chamfer_start = (head_chamfer_dx, R_inscribed)
    head_chamfer_end   = (0, R_circ)

    # Верхняя грань головки
    line_top = msp.add_line((L_SHANK, R_inscribed),
                            head_chamfer_start,
                            dxfattribs={'layer': 'Main'})
    # Фаска на торце головки
    line_ch = msp.add_line(head_chamfer_start, head_chamfer_end,
                           dxfattribs={'layer': 'Main'})
    # Торец головки (вертикаль)
    line_left = msp.add_line(head_chamfer_end, (0, 0),
                             dxfattribs={'layer': 'Main'})
    # Ступенька головка→стержень
    line_step = msp.add_line((L_SHANK, R_inscribed),
                             (L_SHANK, D / 2),
                             dxfattribs={'layer': 'Main'})
    # Симметрия
    for ln in [line_top, line_ch, line_left, line_step]:
        sym = ln.copy()
        msp.add_entity(sym)
        sym.scale(1, -1, 1)
    return head_chamfer_start, head_chamfer_end

def draw_thread(msp, D, L, CHAMFER_TIP, L_THREAD):
    D2_radius    = D / 2 * 0.84
    x_thread_end = L - L_THREAD
    # Линия внутреннего диаметра (тонкая, слой Thread)
    line_inner = msp.add_line(
        (x_thread_end, D2_radius),
        (L - CHAMFER_TIP, D2_radius),
        dxfattribs={'layer': 'Thread'})
    
    # Граница резьбы — вертикаль (сплошная)
    line_runout = msp.add_line(
        (x_thread_end, D2_radius),
        (x_thread_end, D / 2),
        dxfattribs={'layer': 'Thread'})
    
    # Граница резьбы — штриховая (до оси)
    line_dashed = msp.add_line(
        (x_thread_end, D2_radius),
        (x_thread_end, 0),
        dxfattribs={'layer': 'Thread', 'linetype': 'DASHED'})
    
    # Симметрия
    for ln in [line_inner, line_runout, line_dashed]:
        sym = ln.copy()
        msp.add_entity(sym)
        sym.scale(1, -1, 1)
    return x_thread_end


def draw_side_view(msp, L, S_key, R_inscribed, R_circ):
    x_offset_side = L + VIEW_GAP + R_circ
    verts = hex_vertices(x_offset_side, 0, R_circ)
    # 6 сторон шестигранника
    for i in range(6):
        msp.add_line(verts[i], verts[(i+1) % 6],
                     dxfattribs={'layer': 'Main'})
    # 3 диагонали (вершина→противоположная)
    for i in range(3):
        msp.add_line(verts[i], verts[i+3],
                     dxfattribs={'layer': 'Main'})
    # Вписанная и описанная окружности
    msp.add_circle((x_offset_side, 0), R_inscribed,
                   dxfattribs={'layer': 'Main'})
    msp.add_circle((x_offset_side, 0), R_circ,
                   dxfattribs={'layer': 'Main'})
    # Осевые линии вида сбоку
    msp.add_line((x_offset_side - R_circ - AXIS_OVERHANG, 0),
                 (x_offset_side + R_circ + AXIS_OVERHANG, 0),
                 dxfattribs={'layer': 'Axises'})
    msp.add_line((x_offset_side, -R_circ - AXIS_OVERHANG),
                 (x_offset_side,  R_circ + AXIS_OVERHANG),
                 dxfattribs={'layer': 'Axises'})
    return x_offset_side


def draw_dimensions(msp, D, L, L_SHANK, L_THREAD, R_circ,
                    R_inscribed, CHAMFER_TIP, x_thread_end,
                    head_chamfer_start, head_chamfer_end,
                    x_offset_side):
    ov = {'dimlfac':1,'dimtxt':2.5,'dimtad':0,
          'dimtvp':0,'dimdle':0,'dimblk':'EZ_ARROW_FILLED'}
    base_y = D / 2 + 7.5
    # Фаска торца: CHAMFER_TIP x45°
    d1 = msp.add_linear_dim(
        base=(L, D/2+7.5-CHAMFER_TIP),
        p1=(L, D/2-CHAMFER_TIP), p2=(L-CHAMFER_TIP, D/2),
        dimstyle='STANDARD', override=ov,
        text=str(CHAMFER_TIP)+'x45°',
        dxfattribs={'layer':'Measure'})
    d1.set_location(location=(2,1.72), relative=True)
    d1.render()

    # Длина резьбы
    d2 = msp.add_linear_dim(
        base=(L, base_y), p1=(L, D/2), p2=(x_thread_end, D/2),
        dimstyle='STANDARD', override=ov,
        dxfattribs={'layer':'Measure'})
    d2.render()
    # Полная длина болта
    d3 = msp.add_linear_dim(
        base=(L, base_y+7.5), p1=(L, D/2), p2=(0, D/2),
        dimstyle='STANDARD', override=ov,
        dxfattribs={'layer':'Measure'})
    d3.render()
    # Обозначение резьбы M<D>
    d4 = msp.add_linear_dim(
        base=(L+7.5, D/2), p1=(L-CHAMFER_TIP, D/2),
        p2=(L-CHAMFER_TIP, -D/2), text='M'+str(D),
        dimstyle='STANDARD', angle=90, override=ov,
        dxfattribs={'layer':'Thread'})
    d4.render()

    # Размер под ключ (вид сбоку)
    d5 = msp.add_linear_dim(
        base=(x_offset_side, -(R_inscribed+7.5)),
        p1=(x_offset_side-R_inscribed, 0),
        p2=(x_offset_side+R_inscribed, 0),
        dimstyle='STANDARD', override=ov,
        dxfattribs={'layer':'Measure'})
    d5.render()

def generate_bolt_script(D, L, S_key, H_HEAD, CHAMFER_TIP,
                          L_THREAD, HEAD_CHAMFER_DEG):
    """Генерирует читаемый Python-скрипт для воспроизведения чертежа болта."""
    script = f'''# Bolt drawing script: M{D}, L={round(L, 1)}mm
# Generated by bolt-dxf-generator
import ezdxf
from math import tan, radians, cos
import os
 
VIEW_GAP = 30
AXIS_OVERHANG = 5.0
D = {D}
L = {round(L, 1)}
S_key = {S_key}
H_HEAD = {H_HEAD}
CHAMFER_TIP = {CHAMFER_TIP}
L_THREAD = {round(L_THREAD, 1)}
HEAD_CHAMFER_DEG = {HEAD_CHAMFER_DEG}
R_inscribed = S_key / 2.0
R_circ = R_inscribed / cos(radians(30))
L_SHANK = round(L - H_HEAD, 3)
 
doc = ezdxf.new('R2010', setup=True, units=4)
msp = doc.modelspace()
doc.layers.add(name='Main',    color=7, linetype='CONTINUOUS', lineweight=50)
doc.layers.add(name='Thread',  color=4, linetype='CONTINUOUS', lineweight=25)
doc.layers.add(name='Hatches', color=8, linetype='CONTINUOUS', lineweight=25)
doc.layers.add(name='Axises',  color=6, linetype='CENTER')
doc.layers.add(name='Measure', color=170, lineweight=25)
 
# === SHANK ===
msp.add_line((-AXIS_OVERHANG, 0), (L + AXIS_OVERHANG, 0), dxfattribs={{'layer': 'Axises'}})
shank_top_start = (L_SHANK, D / 2)
shank_chamfer_x = L - CHAMFER_TIP
shank_top_end = (shank_chamfer_x, D / 2)
line_top = msp.add_line(shank_top_start, shank_top_end, dxfattribs={{'layer': 'Main'}})
chamfer_start = shank_top_end
chamfer_end = (L, D / 2 - CHAMFER_TIP)
line_ch = msp.add_line(chamfer_start, chamfer_end, dxfattribs={{'layer': 'Main'}})
line_tip = msp.add_line(chamfer_end, (L, 0), dxfattribs={{'layer': 'Main'}})
for ln in [line_top, line_ch, line_tip]:
    sym = ln.copy(); msp.add_entity(sym); sym.scale(1, -1, 1)
 
# === HEAD ===
head_chamfer_dy = R_circ - R_inscribed
head_chamfer_dx = tan(radians(HEAD_CHAMFER_DEG)) * head_chamfer_dy
head_chamfer_start = (head_chamfer_dx, R_inscribed)
head_chamfer_end = (0, R_circ)
line_h_top = msp.add_line((L_SHANK, R_inscribed), head_chamfer_start, dxfattribs={{'layer': 'Main'}})
line_h_ch = msp.add_line(head_chamfer_start, head_chamfer_end, dxfattribs={{'layer': 'Main'}})
line_h_left = msp.add_line(head_chamfer_end, (0, 0), dxfattribs={{'layer': 'Main'}})
line_h_step = msp.add_line((L_SHANK, R_inscribed), (L_SHANK, D / 2), dxfattribs={{'layer': 'Main'}})
for ln in [line_h_top, line_h_ch, line_h_left, line_h_step]:
    sym = ln.copy(); msp.add_entity(sym); sym.scale(1, -1, 1)
 
# === THREAD ===
D2_radius = D / 2 * 0.84
x_thread_end = L - L_THREAD
line_inner = msp.add_line((x_thread_end, D2_radius), (L - CHAMFER_TIP, D2_radius), dxfattribs={{'layer': 'Thread'}})
line_runout = msp.add_line((x_thread_end, D2_radius), (x_thread_end, D / 2), dxfattribs={{'layer': 'Thread'}})
line_dashed = msp.add_line((x_thread_end, D2_radius), (x_thread_end, 0), dxfattribs={{'layer': 'Thread', 'linetype': 'DASHED'}})
for ln in [line_inner, line_runout, line_dashed]:
    sym = ln.copy(); msp.add_entity(sym); sym.scale(1, -1, 1)
 
# === SIDE VIEW ===
from math import sin
x_offset_side = L + VIEW_GAP + R_circ
verts = [(x_offset_side + R_circ * cos(radians(90 + 60 * i)),
          R_circ * sin(radians(90 + 60 * i))) for i in range(6)]
for i in range(6):
    msp.add_line(verts[i], verts[(i+1) % 6], dxfattribs={{'layer': 'Main'}})
for i in range(3):
    msp.add_line(verts[i], verts[i+3], dxfattribs={{'layer': 'Main'}})
msp.add_circle((x_offset_side, 0), R_inscribed, dxfattribs={{'layer': 'Main'}})
msp.add_circle((x_offset_side, 0), R_circ, dxfattribs={{'layer': 'Main'}})
 
os.makedirs('./output_bolts', exist_ok=True)
doc.saveas('./output_bolts/bolt_M{D}_L{round(L,1)}.dxf')
print('Done: M{D} L={round(L,1)}')
'''
    return script
 
 
def generate_step_model(D, L, S_key, H_HEAD, CHAMFER_TIP, L_THREAD):
    """Генерирует 3D-модель болта в формате STEP через cadquery."""
    R_inscribed = S_key / 2.0
    L_SHANK = L - H_HEAD
 
    # Головка: шестигранная призма
    head = (
        cq.Workplane("XY")
        .polygon(6, S_key)
        .extrude(H_HEAD)
    )
 
    # Стержень: цилиндр
    shank = (
        cq.Workplane("XY")
        .workplane(offset=H_HEAD)
        .circle(D / 2)
        .extrude(L_SHANK)
    )
 
    bolt = head.union(shank)
    return bolt   

BOLT_PARAMS = [
    (20, 30, 12.5),  # M20
    (24, 36, 15.0),  # M24
    (27, 41, 17.0),  # M27
    (30, 46, 18.7),  # M30
    (36, 55, 22.5),  # M36
]
L_START, L_END, L_STEP = 80, 80, 9.73
os.makedirs('./output_bolts', exist_ok=True)

L = L_START
while L <= L_END:
    for (D, S_key, H_HEAD) in BOLT_PARAMS:
        timestr   = time.strftime('%Y%m%d-%H%M%S-')
        random.seed(time.process_time())
        CHAMFER_TIP      = round(random.uniform(1.0, 3.0), 1)
        L_THREAD         = round(random.uniform(0.4*L, 0.7*L), 1)
        HEAD_CHAMFER_DEG = round(random.uniform(13, 39), 1)
        R_inscribed = S_key / 2.0
        R_circ      = R_inscribed / cos(radians(30))
        L_SHANK     = round(L - H_HEAD, 3)

        # 1. DXF
        doc, msp = create_doc_and_layers()
        draw_shank(msp, D, L, CHAMFER_TIP, L_SHANK)
        hcs, hce = draw_head(msp, D, L, L_SHANK,
                             R_inscribed, R_circ, HEAD_CHAMFER_DEG)
        x_te = draw_thread(msp, D, L, CHAMFER_TIP, L_THREAD)
        x_os = draw_side_view(msp, L, S_key, R_inscribed, R_circ)
        draw_dimensions(msp, D, L, L_SHANK, L_THREAD, R_circ,
                        R_inscribed, CHAMFER_TIP, x_te,
                        hcs, hce, x_os)
        dxf_path = './output_bolts/' + timestr + '1.dxf'
        doc.saveas(dxf_path)
        print(f'DXF saved: D={D}, L={round(L,1)}')
 
        # 2. Python-скрипт (читаемый)*3.py 
        script_readable = generate_bolt_script(
            D, L, S_key, H_HEAD, CHAMFER_TIP, L_THREAD, HEAD_CHAMFER_DEG)
        py_path = './output_bolts/' + timestr + '3.py'
        with open(py_path, 'w', encoding='utf-8') as f:
            f.write(script_readable)
        print(f'PY  saved: D={D}, L={round(L,1)} → {py_path}')
 
        #  3. Python-скрипт (минифицированный) *4.py 
        try:
            minified = python_minifier.minify(script_readable)
            mini_path = './output_bolts/' + timestr + '4.py'
            with open(mini_path, 'w', encoding='utf-8') as f:
                f.write(minified)
            print(f'MIN saved: D={D}, L={round(L,1)} → {mini_path}')
        except Exception as e:
            print(f'Minify error: {e}')
 
        #  4. STEP 3D-модель 
        try:
            bolt_model = generate_step_model(
                D, L, S_key, H_HEAD, CHAMFER_TIP, L_THREAD)
            step_path = './output_bolts/' + timestr + '4.step'
            exporters.export(bolt_model, step_path)
            print(f'STP saved: D={D}, L={round(L,1)} → {step_path}')
        except Exception as e:
            print(f'STEP error: {e}')
 
        time.sleep(0.9)
    L = round(L + L_STEP, 3)
 
