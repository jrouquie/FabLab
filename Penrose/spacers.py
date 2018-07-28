#!/usr/bin/python
# coding: utf-8

# The goal of this code is to generate suitable spacers (/croisillons/) to make a physical Penrose tiling in a bathroom.
# (We can't use the generic cross-shaped spacers...)
# Inspired by http://images.math.cnrs.fr/Un-parquet-de-Penrose.html where (wooden) tiles touch each other,
# but here we need a small space between tiles (we chose 3mm) and thus those spacers.

# requirements:
# sudo apt install gir1.2-rsvg-2.0 python3-cairo python-gobject-2-dev python-gi-cairo
# pip2 install shapely

# /usr/bin/python2 spacers.py
scale = 100/35.27 # This scales 1 svg unit (pixel) to 1mm

################################################################################
# params
paperwidth, paperheight = 163 *scale, 27 *scale   # as mm. «paper» will actually be Plexiglas.
grout_width = scale * 3 # 3mm (french for grout is /joint/)
spacer_length = grout_width * 4
lozenge_fat_width = scale * 50
# nb_repetitions_lozenges = 18 # how many pairs of slim+fat lozenge to place on paper
nb_repetitions_lozenges = 0 # how many pairs of slim+fat lozenge to place on paper
nb_repetitions_spacers  = 1  # how many sets of 64 spacers to place on paper

################################################################################
# imports
import math, random, sys
import cairo # the alternative library cairocffi seems not supported by rsvg.Handle.render_cairo()

# import rsvg
# `gi.repository` is a special Python package that dynamically generates objects 
from gi.repository import Rsvg

import xml.etree.ElementTree as ET

# We use shapely for high level geometry computations.
# Another Python geometry package, sympy, does symbolic computation and is said to get slow.
import shapely.geometry, shapely.affinity, shapely.prepared
import shapely.speedups
shapely.speedups.enable() # Should be done by default whenever shapely.speedups.available

################################################################################
# Build the shapes

####################
# Spacers
# .buffer computes the points at distance at most grout_width/2, approximating quarter-circles with 3 points
branch = shapely.geometry.LineString([(0,0),(spacer_length,0)])\
    .buffer(grout_width/2, resolution=3)

def spacer(angles):
    """eg spacer([4,2,3])"""
    branches = shapely.geometry.Polygon(branch)
    angle = 0
    for angle_incr in angles:
        angle += angle_incr * 36 # π/5
        rotated_branch = shapely.affinity.rotate(branch, angle, origin=(0,0), use_radians=False)
        # origin can be ‘center’ (BOUNDING BOX center, default), ‘centroid’ (geometry’s centroid), Point, or (x0, y0).
        branches = branches.union(rotated_branch)
    return branches

# approximated from manual counting on a tiling
# vertex are numbered according to http://images.math.cnrs.fr/IMG/jpg/vertex_atlas.jpg
proportions = [27, 70, 17, 11, 44, 9, 12]
proportions = [ 9, 23,  6,  4, 15, 3,  4] # approximated from previous list
def spacers(nb_repetitions=1):
    return [spacer([4,4,2])]        *proportions[0] * nb_repetitions \
         + [spacer([3,3,4])]        *proportions[1] * nb_repetitions \
         + [spacer([4,2,2,2])]      *proportions[2] * nb_repetitions \
         + [spacer([2,2,2,2,2])]    *proportions[3] * nb_repetitions \
         + [spacer([1,2,1,3,3])]    *proportions[4] * nb_repetitions \
         + [spacer([1,1,2,2,2,2])]  *proportions[5] * nb_repetitions \
         + [spacer([1,1,2,1,1,2,2])]*proportions[6] * nb_repetitions

####################
# Lozenges
a = (lozenge_fat_width -grout_width)/2
band1 = shapely.geometry.Polygon([(-3*a,-a), (-3*a,a), (3*a,a), (3*a,-a)])
band2 = shapely.affinity.rotate(band1,72,(0,0))
lozenge_fat = band1.intersection(band2)

phi = (math.sqrt(5) +1)/2
a = (lozenge_fat_width/phi  -grout_width) /2
band1 = shapely.geometry.Polygon([(-3*a,-a), (-3*a,a), (3*a,a), (3*a,-a)])   # same as for lozenge_fat
band2 = shapely.affinity.rotate(band1,36,(0,0))
lozenge_slim = band1.intersection(band2)

def lozenges(nb_repetitions=1):
    return [lozenge_fat] * nb_repetitions + [lozenge_slim] * nb_repetitions

################################################################################
# Place the shapes on the sheet
def tetris_pack(geoms, width, stepx, stepy, nb_orientations):
    """Inside the sheet of paper of the given width, we "drop" the pieces [geoms] like in tetris:
    find the minimum y such that the piece does not intersect with the already fallen pieces.
    We try each column (there are width/stepx of them) and each orientation (there are nb_orientations of them),
      and chose the one letting the piece fall as low as possible.
    (Note that the y axis in shapely is downwards,
    so on the final drawing only, "falling" and "decreasing y" actually mean towards the top of the sheet.
    But our vocabulary (and intuition) seems more suited to describe falling pieces so we ignore this axis orientation, like Jupyter does.).
    geoms must have their branches meeting at (0,0)."""
    result = shapely.geometry.MultiPolygon()
    simplified_result = shapely.geometry.MultiPolygon()   # used to check if a falling piece intersects result
    simplified_result_prepared = shapely.prepared.prep(simplified_result)   # used to check if a falling piece intersects result
    nb_stepx = int(width/stepx)
    starting_yoffs = [0] * nb_stepx # "water level": a lower bound on the height of already fallen pieces, in each column
    nb_placed = 0                   # to report progress to the user
    global_maxy = 0
    for geom in geoms:              # place each piece one by one
        possible_positions = []
        for i in range(nb_orientations): # try all orientations
            geom_rotated = shapely.affinity.rotate(geom, 360/nb_orientations*i, origin=(0,0))
            minx,miny,maxx,maxy = geom_rotated.bounds
            for x in range( int(math.ceil(-minx/stepx)),  int(math.floor((width-maxx)/stepx)) ): # try each column
                geom_xshifted = shapely.affinity.translate(geom_rotated, x*stepx, yoff=-miny)
                yoff=starting_yoffs[x] # no need to check lower than that
                geom_yshifted = geom_xshifted
                while simplified_result_prepared.intersects(geom_yshifted): # move the piece up until it fits
                    # (a better test would be not(.disjoint) or .touches)
                    yoff += stepy
                    geom_yshifted = shapely.affinity.translate(geom_xshifted, xoff=0, yoff=yoff)
                possible_positions.append({'x':x, 'yoff':yoff, 'maxy':yoff+maxy-miny, 'geom':geom_yshifted})
        best_position = min(possible_positions, key = lambda d: (d['maxy'], d['x']))
        starting_yoffs[best_position['x']] = best_position['yoff']
        result = result.union(best_position['geom'])
        simplified_result = simplified_result.union(best_position['geom'])

        # trade some compacity for speed: also add to simplified_result all points below miny of the newly placed piece
        minx,miny,maxx,maxy = best_position['geom'].bounds
        simplified_result = simplified_result.union(
            shapely.geometry.Polygon([(minx,-1e-6), (minx,miny-1e-6), (maxx,miny-1e-6), (maxx,-1e-6)]))
        for x in range( int(math.ceil(minx/stepx)),  int(math.floor(maxx/stepx)) ):
            starting_yoffs[x] = max(starting_yoffs[x], miny)

        simplified_result_prepared = shapely.prepared.prep(simplified_result) # this makes intersection tests more efficient
        nb_placed+=1
        global_maxy = max(maxy, global_maxy)
        sys.stdout.write("\rPlaced:{}, current max y: {:.0f}mm".format(nb_placed, global_maxy/scale)); sys.stdout.flush()
    return result

####################
to_place = lozenges(nb_repetitions=nb_repetitions_lozenges) + spacers(nb_repetitions=nb_repetitions_spacers)
random.seed(); random.shuffle(to_place);

# quick run for debugging:
# to_place = spacers(); random.shuffle(to_place); paperwidth = paperwidth/3
# to_place = to_place[0:70];

print ("To place:{}".format(len(to_place)))
packing = tetris_pack(to_place, paperwidth, 3*scale, 3*scale, 10)
sys.stdout.write("\n")

################################################################################
# Output the result with cairo
def fix_svg(svg):
    """Shapely.geometry.svg() allows to specify only stroke-width and fill color.
    Here we also specify mandatory params for the laser cutter: opacity and stroke color."""
    xml = ET.fromstring(svg)
    for x in xml.findall('path'):
        x.attrib['fill'] = '#ffffff'
        x.attrib['stroke-width'] = '1'
        x.attrib['opacity'] = '1'
        x.attrib['stroke'] = '#ff0000'
    return ET.tostring(xml)

def render_shapely_to_cairo(geom, context):
    minx, miny, maxx, maxy = geom.bounds
    svg = fix_svg(geom.svg())
    svg = '<svg viewBox="{} {} {} {}">'.format(minx,miny,maxx,maxy) + svg + '</svg>'
    svg = Rsvg.Handle.new_from_data(svg)
    svg.render_cairo(context)

for surface in [
        cairo.PDFSurface("spacers.pdf", paperwidth, paperheight),
        # cairo.PSSurface ("spacers.ps",  paperwidth, paperheight),
        cairo.SVGSurface("spacers.svg", paperwidth, paperheight)]:
    ctx = cairo.Context(surface)
    render_shapely_to_cairo(packing, ctx)

ctx.show_page()
