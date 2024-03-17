from panda3d.core import NodePath, Shader, OmniBoundingVolume

from random import Random
from math import pi


NUM_RINGS = 60
X_SPACING = 2
Y_SPACING = 10
SPEED = 10
AR_FACTOR = pi

SEQ_LENGTH = 10


shader = Shader.load(Shader.SL_GLSL, "assets/glsl/tube.vert", "assets/glsl/tube.frag")


class Ring:
    def __init__(self):
        self.is_trench = False

    def radius_at(self, y):
        t = (y - self.node_path.get_y()) / Y_SPACING + 0.5
        t = max(0, min(1, t))
        return self.end_radius * t + self.start_radius * (1 - t)

    def needs_cull(self):
        return self.node_path.get_y() < -Y_SPACING


class Tube:
    def __init__(self, seed=0):
        self.root = NodePath("root")
        self.root.set_shader(shader)
        self.root.node().set_final(True)
        self.root.node().set_bounds(OmniBoundingVolume())
        self.random = Random(seed)
        self.y = 0
        self.counter = 0
        self.rings = []

        self.next_radius = 80

        model = loader.load_model('assets/bam/segments.bam')
        self.trenches = model.find_all_matches('trench_*')
        self.tiles = model.find_all_matches('tile_*')
        self.empty_tiles = [self.tiles[0]]

        # Always start with empty
        self.gen_ring(self.empty_tiles)
        self.gen_ring(self.empty_tiles)

        while len(self.rings) < NUM_RINGS:
            self.gen_sequence()

        taskMgr.add(self.task)

    @property
    def current_ring(self):
        for ring in self.rings:
            if ring.node_path.get_y() > -Y_SPACING / 2.0:
                return ring

    @property
    def radius(self):
        return self.rings[0].start_radius

    def task(self, task):
        y = task.time * SPEED
        if self.y == 0:
            dy = 0
        else:
            dy = y - self.y

        self.y = y

        self.root.set_shader_input('y', self.y)

        for i, ring in enumerate(self.rings):
            new_y = ring.node_path.get_y() - dy
            ring.node_path.set_y(new_y)

        while self.rings and self.rings[0].needs_cull():
            ring = self.rings.pop(0)
            ring.node_path.remove_node()

        while len(self.rings) < NUM_RINGS:
            self.gen_sequence()

        return task.cont

    def gen_sequence(self):
        opts = ['regular', 'trench', 'ramp']

        # Don't put stepdown right after ramp
        if self.rings and self.rings[-1].start_radius == self.rings[-1].end_radius:
            opts.append('stepdown')

        stype = self.random.choice(opts)

        if stype == 'regular':
            for i in range(SEQ_LENGTH):
                self.gen_ring(self.tiles)

        elif stype == 'trench':
            for i in range(SEQ_LENGTH):
                self.gen_ring(self.trenches)

        elif stype == 'ramp':
            for i in range(1):
                self.gen_ring(self.empty_tiles, radius_delta=-1)

        elif stype == 'stepdown':
            self.next_radius += 1
            self.gen_ring(self.empty_tiles)

    def gen_ring(self, set, radius_delta=0):
        from_radius = self.next_radius
        to_radius = from_radius + radius_delta
        count = int(to_radius * AR_FACTOR + 0.5)

        ring = Ring()
        ring.num_segments = count
        ring.start_radius = from_radius
        ring.end_radius = to_radius

        np = NodePath("ring")
        np.set_shader_input("num_segments", count)
        np.set_shader_input("radius", (from_radius, to_radius))
        np.node().set_final(True)
        ring.node_path = np

        # for count = 4
        for c in range(count):
            seg = self.random.choice(set)
            seg = seg.copy_to(np)
            seg.set_pos(c * X_SPACING, 0, 0)

        np.flatten_strong()
        np.set_y(self.counter * Y_SPACING - self.y)
        np.reparent_to(self.root)
        self.rings.append(ring)
        self.counter += 1
        self.next_radius = to_radius
        return np
