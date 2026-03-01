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
