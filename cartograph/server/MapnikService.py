import os

import mapnik

from cartograph import Config

from math import pi, cos, sin, log, exp, atan

from cartograph.server.CacheService import CacheService

DEG_TO_RAD = pi / 180
RAD_TO_DEG = 180 / pi


def minmax(a, b, c):
    a = max(a, b)
    a = min(a, c)
    return a

class GoogleProjection:
    def __init__(self, levels=18):
        self.Bc = []
        self.Cc = []
        self.zc = []
        self.Ac = []
        c = 256
        for d in range(0, levels):
            e = c / 2
            self.Bc.append(c / 360.0)
            self.Cc.append(c / (2 * pi))
            self.zc.append((e, e))
            self.Ac.append(c)
            c *= 2

    def fromLLtoPixel(self, ll, zoom):
        d = self.zc[zoom]
        e = round(d[0] + ll[0] * self.Bc[zoom])
        f = minmax(sin(DEG_TO_RAD * ll[1]), -0.9999, 0.9999)
        g = round(d[1] + 0.5 * log((1 + f) / (1 - f)) * -self.Cc[zoom])
        return (e, g)

    def fromPixelToLL(self, px, zoom):
        e = self.zc[zoom]
        f = (px[0] - e[0]) / self.Bc[zoom]
        g = (px[1] - e[1]) / -self.Cc[zoom]
        h = RAD_TO_DEG * (2 * atan(exp(g)) - 0.5 * pi)
        return (f, h)

class LayerService:
    def __init__(self, xmlPath):
        self.m = mapnik.Map(256, 256)
        mapnik.load_map(self.m, xmlPath, True)
        self.layers = { l.name : i for (i, l) in enumerate(self.m.layers) }
        assert 'countries' in self.layers
        assert 'contours' in self.layers
        self.prj = mapnik.Projection(self.m.srs)
        self.tileproj = GoogleProjection(19)

    def renderTile(self, tile_uri, z, x, y):

        # Calculate pixel positions of bottom-left & top-right
        p0 = (x * 256, (y + 1) * 256)
        p1 = ((x + 1) * 256, y * 256)

        # Convert to LatLong (EPSG:4326)
        l0 = self.tileproj.fromPixelToLL(p0, z)
        l1 = self.tileproj.fromPixelToLL(p1, z)

        # Convert to map projection (e.g. mercator co-ords EPSG:900913)
        c0 = self.prj.forward(mapnik.Coord(l0[0], l0[1]))
        c1 = self.prj.forward(mapnik.Coord(l1[0], l1[1]))

        # Bounding box for the tile
        bbox = mapnik.Box2d(c0.x, c0.y, c1.x, c1.y)

        render_size = 512
        self.m.resize(render_size, render_size)
        self.m.zoom_to_box(bbox)
        if self.m.buffer_size < 256:
            self.m.buffer_size = 256

        # Render image with default Agg renderer
        im = mapnik.Image(render_size, render_size)
        mapnik.render(self.m, im)
        im.save(tile_uri, 'png256')

class MapnikService:
    def __init__(self, conf):
        self.maps = {}
        self.conf = conf
        self.cache = CacheService(conf)
        for name in self.conf.get('Metrics', 'active').split():
            xml = os.path.join(self.conf.get('DEFAULT', 'mapDir'), name + '.xml')
            self.maps[name] = LayerService(xml)

    def on_get(self, req, resp, layer, z, x, y):
        z, x, y = map(int, [z, x, y])
        if self.cache.serveFromCache(req, resp):
            return
        path = self.cache.getCachePath(req)
        d = os.path.dirname(path)
        if not os.path.isdir(d): os.makedirs(d)
        self.maps[layer].renderTile(path, z, x, y)
        r = self.cache.serveFromCache(req, resp)
        assert(r)

#
# if __name__ == '__main__':
#     Config.initConf('data/conf/simple.txt')
#     s = MapnikServer('data/simple/maps/base.xml')
#     s.render_tile('tile1.png', 32, 32, 6)
#     s = MapnikServer('data/simple/maps/gender.xml')
#     s.render_tile('tile2.png', 32, 32, 6)


