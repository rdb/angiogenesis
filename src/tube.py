from panda3d.core import NodePath, Shader, OmniBoundingVolume

from random import Random
from math import pi


NUM_RINGS = 60
X_SPACING = 2
Y_SPACING = 10
SPEED = 10
AR_FACTOR = pi
MIN_SEG_COUNT = 6

SEQ_LENGTH = 10


shader = Shader.load(Shader.SL_GLSL, "assets/glsl/tube.vert", "assets/glsl/tube.frag")


class Ring:
    def __init__(self):
        pass

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

        self.seg_count = 300

        model = loader.load_model('assets/bam/segments.bam')
        self.passable_trenches = model.find_all_matches('trench_corridor*')
        self.impassable_trenches = model.find_all_matches('trench_impassable*')
        self.tiles = model.find_all_matches('tile_*')
        self.empty_tiles = [self.tiles[0]]

        # Always start with empty
        self.gen_empty_ring()
        self.gen_empty_ring()

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
        opts = ['regular', 'trench']

        if self.seg_count > MIN_SEG_COUNT:
            opts.append('ramp')

        # Don't put stepdown right after ramp
        if self.rings and self.rings[-1].start_radius == self.rings[-1].end_radius:
            opts.append('stepdown')

        stype = self.random.choice(opts)

        if stype == 'regular':
            for i in range(SEQ_LENGTH):
                self.gen_ring(self.random.choices(self.tiles, k=self.seg_count))

        elif stype == 'trench':
            self.gen_trench()

        elif stype == 'ramp':
            self.gen_empty_ring(delta=-1)

        elif stype == 'stepdown':
            self.seg_count += 1
            self.gen_empty_ring()

    def gen_empty_ring(self, delta=0):
        segs = self.random.choices(self.empty_tiles, k=self.seg_count + delta)
        self.gen_ring(segs)

    def gen_trench(self):
        segs_passability = self.random.choices((True, False), k=self.seg_count)
        for i in range(SEQ_LENGTH):
            segs = [self.random.choice(self.passable_trenches if p else self.impassable_trenches) for p in range(self.seg_count)]
            self.gen_ring(segs)

    def gen_ring(self, set):
        count = len(set)
        from_radius = self.seg_count / AR_FACTOR
        to_radius = count / AR_FACTOR

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
        for c, seg in enumerate(set):
            seg = seg.copy_to(np)
            seg.set_pos(c * X_SPACING, 0, 0)

        np.flatten_strong()
        np.set_y(self.counter * Y_SPACING - self.y)
        np.reparent_to(self.root)
        self.rings.append(ring)
        self.counter += 1
        self.seg_count = count
        return np
