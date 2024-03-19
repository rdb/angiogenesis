from panda3d.core import NodePath, Shader, OmniBoundingVolume, NodePathCollection

from random import Random
from math import pi


NUM_RINGS = 60
X_SPACING = 2
Y_SPACING = 40
SPEED = 10
AR_FACTOR = pi
MIN_SEG_COUNT = 6

SEQ_LENGTH = 10
SHIP_TRENCH_LOWERING = 0.75


shader = Shader.load(Shader.SL_GLSL, "assets/glsl/tube.vert", "assets/glsl/tube.frag")


class Ring:
    def __init__(self):
        self.collision_nodes = []
        self.r_to_x = 1

    def radius_at(self, y):
        t = (y - self.node_path.get_y()) / Y_SPACING + 0.5
        #t = max(0, min(1, t))
        return self.end_radius * t + self.start_radius * (1 - t)

    def needs_cull(self):
        return self.node_path.get_y() < -Y_SPACING


class Tube:
    def __init__(self, seed=1):
        self.root = NodePath("root")
        self.root.set_shader(shader)
        self.root.node().set_final(True)
        self.root.node().set_bounds(OmniBoundingVolume())
        self.random = Random(seed)
        self.y = 0
        self.counter = 0
        self.rings = []

        self.seg_count = 150

        model = loader.load_model('assets/bam/segments/segments.bam')

        self.entrance_trenches = []
        self.exit_trenches = []
        self.middle_trenches = []
        self.impassable_trenches = []
        self.tile1s = []
        self.tile3s = []
        self.segments = {}

        for n in model.children:
            name = n.name
            if name.startswith("steel_"):
                name = name[6:]
            else:
                continue

            gnode = n.find("**/+GeomNode")
            gnode.name = name
            gnode.detach_node()

            cnode = n.find("**/+CollisionNode")
            if cnode:
                for i in range(cnode.node().get_num_solids()):
                    cnode.node().modify_solid(i).set_tangible(True)
                cnode.detach_node()
                cnode.hide()
            else:
                cnode = None

            seg = (gnode, cnode)
            self.segments[name] = seg

            if name.startswith('trench3_entrance'):
                self.entrance_trenches.append(seg)
            elif name.startswith('trench3_ending'):
                self.exit_trenches.append(seg)
            elif name.startswith('trench3_middle'):
                self.middle_trenches.append(seg)
            elif name.startswith('trench3_impassable'):
                self.impassable_trenches.append(seg)
            elif name.startswith('tile1_'):
                self.tile1s.append(seg)
            elif name.startswith('tile3_'):
                self.tile3s.append(seg)

        self.empty_tiles = [self.segments['tile1_open.020']]

        self.next_emptyish = False
        self.generator = iter(self.gen_tube())
        next(self.generator)

        taskMgr.add(self.task)

    @property
    def current_ring(self):
        for ring in self.rings:
            if ring.node_path.get_y() > -Y_SPACING / 2.0:
                return ring

    @property
    def next_ring(self):
        take_next = False
        for ring in self.rings:
            if take_next:
                return ring
            if ring.node_path.get_y() > -Y_SPACING / 2.0:
                take_next = True

        return next(self.generator)

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
            next(self.generator)

        return task.cont

    def gen_tube(self):
        # Always start with empty
        yield self.gen_empty_ring()
        #yield self.gen_empty_ring()

        while True:
            yield from self.gen_sequence()

    def gen_sequence(self):
        opts = ['wall1']

        if not self.next_emptyish:
            opts += ['wall2', 'tile3', 'trench']
        self.next_emptyish = False

        # Don't put stepdown right after ramp
        if self.rings and self.rings[-1].start_radius == self.rings[-1].end_radius:
            if self.seg_count > MIN_SEG_COUNT:
                opts.append('ramp')

            opts.append('stepdown')

        stype = self.random.choice(opts)

        if stype == 'wall1':
            seg1 = self.segments['tile1_impasssable']
            seg2 = self.segments['tile1_gate']
            segs = [seg1, seg1, seg2, seg1, seg1, seg1]
            self.random.shuffle(segs)
            segs = segs * (self.seg_count // 6)
            while len(segs) < self.seg_count:
                segs.append(seg1)
            yield self.gen_ring(segs)

        elif stype == 'wall2':
            seg1 = self.segments['tile1_impasssable.001']
            seg2 = self.segments['tile1_open']
            segs = [seg1, seg1, seg2, seg1, seg1, seg1]
            self.random.shuffle(segs)
            segs = segs * (self.seg_count // 6)
            while len(segs) < self.seg_count:
                segs.append(seg1)
            yield self.gen_ring(segs)
            self.next_emptyish = True

        elif stype == 'tile3':
            while self.seg_count % 3 != 0:
                yield self.gen_empty_ring(delta=-1)

            for i in range(SEQ_LENGTH):
                yield self.gen_ring(self.random.choices(self.tile3s, k=self.seg_count // 3), width=3)

        elif stype == 'trench':
            yield from self.gen_trench()

        elif stype == 'ramp':
            yield self.gen_empty_ring(delta=self.random.randint(-20, 20))

        elif stype == 'stepdown':
            self.seg_count += 1
            yield self.gen_empty_ring()

    def gen_empty_ring(self, delta=0):
        segs = self.random.choices(self.empty_tiles, k=self.seg_count + delta)
        return self.gen_ring(segs)

    def gen_trench(self):
        while self.seg_count % 3 != 0:
            yield self.gen_empty_ring(delta=-1)

        passability = self.random.choices((True, False), k=self.seg_count // 3)

        segs = [self.random.choice(self.entrance_trenches if p else self.impassable_trenches) for p in passability]
        ring = self.gen_ring(segs, width=3)
        ring.end_radius += SHIP_TRENCH_LOWERING
        yield ring

        for i in range(SEQ_LENGTH):
            segs = [self.random.choice(self.middle_trenches if p else self.impassable_trenches) for p in passability]
            ring = self.gen_ring(segs, width=3)
            ring.start_radius += SHIP_TRENCH_LOWERING
            ring.end_radius += SHIP_TRENCH_LOWERING
            yield ring

        segs = [self.random.choice(self.exit_trenches if p else self.impassable_trenches) for p in passability]
        ring = self.gen_ring(segs, width=3)
        ring.is_trench = True
        ring.start_radius += SHIP_TRENCH_LOWERING
        yield ring

    def gen_ring(self, set, width=1):
        count = len(set) * width
        from_radius = self.seg_count / AR_FACTOR
        to_radius = count / AR_FACTOR

        ring = Ring()
        ring.num_segments = count
        ring.start_radius = from_radius
        ring.end_radius = to_radius
        ring.x_spacing = X_SPACING * width

        np = NodePath("ring")
        np.set_shader_input("num_segments", count)
        np.set_shader_input("radius", (from_radius, to_radius))
        np.node().set_final(True)
        ring.node_path = np

        ring.r_to_x = count * X_SPACING

        for c, (gnode, cnode) in enumerate(set):
            gnode = gnode.copy_to(np)
            gnode.set_pos(c * X_SPACING * width, 0, 0)
            ring.collision_nodes.append(cnode)

        np.flatten_strong()
        np.set_y(self.counter * Y_SPACING - self.y)
        np.reparent_to(self.root)
        self.rings.append(ring)
        self.counter += 1
        self.seg_count = count
        return ring
