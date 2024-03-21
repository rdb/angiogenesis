from panda3d.core import NodePath, Shader, OmniBoundingVolume, NodePathCollection

from random import Random
from math import pi
from enum import Enum

from .util import RingList


class TileNavType:
    PASSABLE = 1
    SWERVIBLE = 2 # sic
    IMPASSABLE = 3


NUM_RINGS = 60
X_SPACING = 2
Y_SPACING = 40
SPEED = 10
AR_FACTOR = pi
MIN_SEG_COUNT = 6
MAX_SWERVE = 6

SEQ_LENGTH = 10
TRENCH_DEPTH = 2.5


shader = Shader.load(Shader.SL_GLSL, "assets/glsl/tube.vert", "assets/glsl/tube.frag")


class Ring:
    def __init__(self):
        self.collision_nodes = []
        self.r_to_x = 1
        self.next_ring = None
        self.start_depth = 0.0
        self.end_depth = 0.0

    def radius_at(self, y):
        t = (y - self.node_path.get_y()) / Y_SPACING + 0.5
        #t = max(0, min(1, t))
        return self.end_radius * t + self.start_radius * (1 - t)

    def depth_at(self, y):
        t = (y - self.node_path.get_y()) / Y_SPACING + 0.5
        #t = max(0, min(1, t))
        return self.end_depth * t + self.start_depth * (1 - t)

    def needs_cull(self):
        return self.node_path.get_y() < -Y_SPACING

    def advance(self, dy):
        new_y = self.node_path.get_y() - dy
        self.node_path.set_y(new_y)
        if self.next_ring:
            self.next_ring.advance(dy)


class Tube:
    def __init__(self, seed=1):
        self.root = NodePath("root")
        self.root.set_shader(shader)
        self.root.node().set_final(True)
        self.root.node().set_bounds(OmniBoundingVolume())
        self.random = Random(seed)
        self.y = 0
        self.counter = 0
        self.first_ring = None
        self.last_ring = None

        model = loader.load_model('assets/bam/segments/segments.bam')

        self.entrance_trenches = []
        self.exit_trenches = []
        self.middle_trenches = []
        self.impassable_trenches = []
        self.tile1_by_type = {
            TileNavType.PASSABLE: [],
            TileNavType.IMPASSABLE: [],
            TileNavType.SWERVIBLE: [],
        }
        self.tile3s = []
        self.segments = {}

        for n in model.children:
            name = n.name
            if name.startswith("steel_"):
                name = name[6:]
            else:
                continue

            cnode = n.find("**/+CollisionNode")
            if cnode:
                for i in range(cnode.node().get_num_solids()):
                    cnode.node().modify_solid(i).set_tangible(True)
                cnode.detach_node()
                cnode.hide()
                for c in cnode.children:
                    c.reparent_to(n)
            else:
                cnode = None

            n.clear_transform()
            n.flatten_strong()

            seg = (n, cnode)
            self.segments[name] = seg

            if name.startswith('trench3_entrance'):
                self.entrance_trenches.append(seg)
            elif name.startswith('trench3_end'):
                self.exit_trenches.append(seg)
            elif name.startswith('trench3_middle'):
                self.middle_trenches.append(seg)
            elif name.startswith('trench3_impassable'):
                self.impassable_trenches.append(seg)
            elif name.startswith('tile1_open'):
                self.tile1_open.append(seg)
            elif name.startswith('tile1_impassable'):
                self.tile1_by_type[TileNavType.IMPASSABLE].append(seg)
            elif name.startswith('tile1_swervible'): # sic
                self.tile1_by_type[TileNavType.SWERVIBLE].append(seg)
            elif name.startswith('tile1_passable'):
                self.tile1_by_type[TileNavType.PASSABLE].append(seg)
            elif name.startswith('tile3_'):
                self.tile3s.append(seg)

        self.empty_tiles = [self.segments['tile1_empty']]

        self.seg_count = 2
        self.next_emptyish = False
        self.generator = iter(self.gen_tube())
        self.last_ring = next(self.generator)
        self.first_ring = self.last_ring

        for i in range(NUM_RINGS):
            next(self.generator)

        taskMgr.add(self.task)

    @property
    def current_ring(self):
        ring = self.first_ring
        while ring is not None:
            if ring.node_path.get_y() > -Y_SPACING / 2.0:
                return ring
            ring = ring.next_ring

    @property
    def next_ring(self):
        ring = self.first_ring
        while ring is not None:
            if ring.node_path.get_y() > -Y_SPACING / 2.0:
                if ring.next_ring is None:
                    return next(self.generator)
                return ring.next_ring
            ring = ring.next_ring

        self.last_ring = next(self.generator)
        return self.last_ring

    def task(self, task):
        y = task.time * SPEED
        if self.y == 0:
            dy = 0
        else:
            dy = y - self.y

        self.y = y

        self.root.set_shader_input('y', self.y)

        self.first_ring.advance(dy)

        ring = self.first_ring
        while ring and ring.needs_cull():
            ring.node_path.remove_node()
            ring = ring.next_ring
            self.first_ring = ring

            # For every ring we remove, create a new one.
            self.last_ring = next(self.generator)

        return task.cont

    def gen_tube(self):
        # Always start with empty
        self.seg_count = 30
        yield self.gen_empty_ring()

        while True:
            yield from self.gen_tile1_section()
            yield self.gen_empty_ring()
            yield from self.gen_trench()
            yield self.gen_empty_ring()

    def gen_tile1_section(self):
        #next_types = RingList(self.random.choices((TileNavType.SWERVIBLE, TileNavType.IMPASSABLE), k=self.seg_count))
        next_types = RingList(self.random.choices((TileNavType.IMPASSABLE, TileNavType.IMPASSABLE, TileNavType.IMPASSABLE, TileNavType.IMPASSABLE, TileNavType.PASSABLE)) * self.seg_count)

        def ensure_passable(types, i, sw_left=0, sw_right=0):
            if types[i] == TileNavType.PASSABLE:
                return

            sw_next = (types[i] == TileNavType.SWERVIBLE)

            if (sw_next or sw_left) and types[i - 1] == TileNavType.PASSABLE:
                return

            if (sw_next or sw_right) and types[i + 1] == TileNavType.PASSABLE:
                return

            if sw_left and sw_next and types[i - 1] == TileNavType.SWERVIBLE and types[i - 2] == TileNavType.PASSABLE:
                return

            if sw_right and sw_next and types[i + 1] == TileNavType.SWERVIBLE and types[i + 2] == TileNavType.PASSABLE:
                return

            choices = [-1, 1]
            if sw_left:
                choices.append(-2)
            if sw_right:
                choices.append(2)

            choice = self.random.choice(choices)
            types[i + choice] = TileNavType.PASSABLE

            if (choice < 0 and not sw_left) or (choice > 0 and not sw_right):
                # To get to this one, need to swerve through the tile ahead
                types[i] = TileNavType.SWERVIBLE

            if abs(choice) == 2:
                # To get to this one, the one between it must also be swervible
                types[i + choice // 2] = TileNavType.SWERVIBLE

        for i in range(self.seg_count):
            ensure_passable(next_types, i, 1, 1)

        for j in range(10):
            segs = [self.random.choice(self.tile1_by_type[next_type]) for next_type in next_types]
            yield self.gen_ring(segs)

            cur_types = next_types
            #next_types = RingList(self.random.choices((TileNavType.SWERVIBLE, TileNavType.IMPASSABLE), k=self.seg_count))
            next_types = RingList(self.random.choices((TileNavType.IMPASSABLE, TileNavType.IMPASSABLE, TileNavType.IMPASSABLE, TileNavType.IMPASSABLE, TileNavType.PASSABLE)) * self.seg_count)
            for i in range(self.seg_count):
                if cur_types[i] == TileNavType.PASSABLE:
                    ensure_passable(next_types, i, cur_types[i - 1] != TileNavType.IMPASSABLE, cur_types[i + 1] != TileNavType.IMPASSABLE)

    def gen_wall1(self):
        seg1 = self.segments['tile1_impassable']
        seg2 = self.segments['tile1_gate']
        segs = [seg1, seg1, seg2, seg1, seg1, seg1]
        self.random.shuffle(segs)
        segs = segs * (self.seg_count // 6)
        while len(segs) < self.seg_count:
            segs.append(seg1)
        yield self.gen_ring(segs)

    def gen_wall2(self):
        seg1 = self.segments['tile1_impassable.001']
        seg2 = self.segments['tile1_open']
        segs = [seg1, seg1, seg2, seg1, seg1, seg1]
        self.random.shuffle(segs)
        segs = segs * (self.seg_count // 6)
        while len(segs) < self.seg_count:
            segs.append(seg1)
        yield self.gen_ring(segs)
        self.next_emptyish = True

    def gen_obstacle(self):
        while self.seg_count % 3 != 0:
            yield self.gen_empty_ring(delta=-1)

    def gen_sequence(self, stype=None):
        if stype is None:
            opts = ['wall1']

            if not self.next_emptyish:
                opts += ['wall2', 'tile3', 'trench']
            self.next_emptyish = False

            # Don't put stepdown right after ramp
            if self.last_ring and self.last_ring.start_radius == self.last_ring.end_radius:
                if self.seg_count > MIN_SEG_COUNT:
                    opts.append('ramp')

                opts.append('stepdown')

            stype = self.random.choice(opts)

        if stype == 'wall1':

            self.gen_wall1()

        elif stype == 'wall2':
            self.gen_wall2()

        elif stype == 'tile3':
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
        if self.seg_count % 3 != 0:
            yield self.gen_empty_ring(delta=-(self.seg_count % 3))
            #assert self.seg_count % 3 == 0

        passability = self.random.choices((True, False), k=self.seg_count // 3)

        segs = [self.random.choice(self.entrance_trenches if p else self.impassable_trenches) for p in passability]
        ring = self.gen_ring(segs, width=3)
        ring.end_depth = TRENCH_DEPTH
        yield ring

        for i in range(SEQ_LENGTH):
            segs = [self.random.choice(self.middle_trenches if p else self.impassable_trenches) for p in passability]
            ring = self.gen_ring(segs, width=3)
            ring.start_depth = TRENCH_DEPTH
            ring.end_depth = TRENCH_DEPTH
            yield ring

        segs = [self.random.choice(self.exit_trenches if p else self.impassable_trenches) for p in passability]
        ring = self.gen_ring(segs, width=3)
        ring.is_trench = True
        ring.start_depth = TRENCH_DEPTH
        yield ring

    def gen_ring(self, set, width=1, branch=None):
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

        if branch is None:
            if self.last_ring is not None:
                self.last_ring.next_ring = ring
            self.last_ring = ring
        else:
            if self.last_ring is not None:
                self.last_ring.next_ring = ring
            self.last_ring = ring

        self.counter += 1
        self.seg_count = count
        return ring
