# coding=utf-8
""" Helper module for geospatial tasks.
"""
import shapely.ops
from shapely.wkt import loads as wkt_loads
from functools import partial
try:
    import pyproj
    PYPROJ_INSTALLED = True
except ImportError:
    PYPROJ_INSTALLED = False


def gml_to_polygon(footprint):
    """Converts a GML footprint into a WKT polygon string.

    Can handle the formats used by Sentinel-1, 2, and 3

    Parameters
    ----------
    footprint : str
        A GML footprint as retrieved from SciHub.

    Returns
    -------
    str
        The converted WKT polygon string.
    """
    footprint = footprint.replace('\n', '').strip()
    coords_poly = []
    #
    # Sentinel-1
    # (http://www.opengis.net/gml/srs/epsg.xml#4326)
    #
    if ',' in footprint:
        coords_gml = footprint.split()
        for coord_pair in coords_gml:
            lat, lon = [float(_) for _ in coord_pair.split(',')]
            if lon < -180.0:
                lon = -180.0
            if lon > 180.0:
                lon = 180.0
            if lat < -90.0:
                lat = -90.0
            if lat > 90.0:
                lat = 90.0
            coords_poly.append('{lon:.4f} {lat:.4f}'.format(lon=lon, lat=lat))

    #
    # Sentinel-3 and Sentinel-2
    # (http://www.opengis.net/def/crs/EPSG/0/4326)
    #
    else:
        coords_gml = footprint.split()
        for i in range(len(coords_gml)//2):
            lat = float(coords_gml[2*i])
            lon = float(coords_gml[2*i+1])
            if lon < -180.0:
                lon = -180.0
            if lon > 180.0:
                lon = 180.0
            if lat < -90.0:
                lat = -90.0
            if lat > 90.0:
                lat = 90.0
            coords_poly.append('{lon:.4f} {lat:.4f}'.format(lon=lon, lat=lat))

    #
    # Make sure the polygon is a closed line string.
    #
    if coords_poly[0] != coords_poly[-1]:
        coords_poly.append(coords_poly[0])

    wkt = 'POLYGON (({}))'.format(','.join(coords_poly))
    return wkt


def polygon_to_lonlat(polygon):
    """Convert a WKT polygon string to a tuple of lat and lon lists.

    Parameters
    ----------
    polygon : str
        A WKT polygon string.

    Returns
    -------
    tuple of lists
        A 2-tuple containing a list of longitudes and a list of latitudes.
    """
    poly_coords = polygon.split('((')[1].split('))')[0].split(',')
    coords = [(float(lon), float(lat)) for lon, lat in
              [co.split(' ') for co in poly_coords]]
    lon, lat = zip(*coords)
    return (lon, lat)


def polygon_area(polygon):
    """Computes the area of a WKT polygon in square kilometers.

    The area computation is done by projecting onto an appropriate equal-area
    projection. It is not exact.

    Parameters
    ----------
    polygon : str
        A WKT polygon string.

    Returns
    -------
    float
        The area of the polygon in square kilometers.
    """
    if not PYPROJ_INSTALLED:
        raise ImportError("`pyproj` must be installed to use this feature!")
    poly = wkt_loads(polygon)
    poly_area = shapely.ops.transform(
        partial(
            pyproj.transform,
            pyproj.Proj(init='EPSG:4326'),
            pyproj.Proj(
                proj='aea',
                lat1=poly.bounds[1],
                lat2=poly.bounds[3]
            )
        ),
        poly
    )
    return poly_area.area / 1e6


def intersect(wkt1, wkt2, tolerance=0):
    """Check whether two geometries specified in WKT format intersect.

    Parameters
    ----------
    wkt1 : str
    wkt2 : str

    Returns
    -------
    bool
        True if the geometries intersect, False otherwise.
    """
    poly1 = wkt_loads(wkt1)
    poly2 = wkt_loads(wkt2)
    if tolerance > 0:
        return poly1.distance(poly2) <= tolerance
    else:
        return poly1.intersects(poly2)
