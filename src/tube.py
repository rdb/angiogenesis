from panda3d.core import (
    NodePath,
    Shader,
    OmniBoundingVolume,
    NodePathCollection,
    CollisionPolygon,
    Vec2,
)

from random import Random
from math import pi, tau, ceil, cos, sin
from enum import Enum

from .util import RingList


class NavType(Enum):
    EMPTY = 0
    PASSABLE = 1
    SWERVIBLE = 2 # sic
    IMPASSABLE = 3
    TUNNEL = 4 # non-swervable but passable

    @property
    def is_passable(self):
        return self in (NavType.EMPTY, NavType.PASSABLE, NavType.TUNNEL)

    @property
    def is_swervible(self): #sic
        return self in (NavType.SWERVIBLE, NavType.PASSABLE, NavType.EMPTY)


LEVEL = 'steel'
LEVELS = 'steel', 'rift', 'flesh'
NUM_RINGS = 30
X_SPACING = 2
Y_SPACING = 40
SPEED = 10
AR_FACTOR = pi
MIN_SEG_COUNT = 6
MAX_SWERVE = 6

SECTION_LENGTH = 3
TRENCH_DEPTH = 2.5


class TileSet:
    def __init__(self):
        self.entrance_trenches = []
        self.exit_trenches = []
        self.middle_trenches = []
        self.impassable_trenches = []
        self.tile1_by_type = {
            NavType.EMPTY: [],
            NavType.PASSABLE: [],
            NavType.IMPASSABLE: [],
            NavType.SWERVIBLE: [],
            NavType.TUNNEL: [],
        }
        self.tile3_by_type = {
            NavType.EMPTY: [],
            NavType.PASSABLE: [],
            NavType.IMPASSABLE: [],
            NavType.SWERVIBLE: [],
            NavType.TUNNEL: [],
        }
        self.tile3s = []
        self.segments = {}

    def add(self, n):
        name = n.name.split('_', 1)[1]

        cnp = n.find("**/+CollisionNode")
        if cnp:
            cnode = cnp.node()
            num_solids = cnode.get_num_solids()
            i = 0
            while i < num_solids:
                solid = cnode.modify_solid(i)
                if isinstance(solid, CollisionPolygon):
                    if should_cull_collision_poly(name, solid):
                        cnode.remove_solid(i)
                        num_solids -= 1
                        continue

                cnode.modify_solid(i).set_tangible(True)
                i += 1

            cnp.detach_node()
            cnp.hide()
            for c in cnp.children:
                c.reparent_to(n)

            if num_solids == 0:
                cnp = None
        else:
            cnp = None

        # Code isn't handling multiple collision nodes yet
        assert not n.find("**/+CollisionNode")
        n.find_all_matches("**/+CollisionNode").detach()

        n.clear_transform()
        n.flatten_strong()

        seg = (n, cnp)
        self.segments[name] = seg

        if name.startswith('trench3_entrance'):
            self.entrance_trenches.append(seg)
        elif name.startswith('trench3_end'):
            self.exit_trenches.append(seg)
        elif name.startswith('trench3_middle'):
            self.middle_trenches.append(seg)
        elif name.startswith('trench3_impassable'):
            self.impassable_trenches.append(seg)
        elif name.startswith('tile1_empty'):
            self.tile1_by_type[NavType.EMPTY].append(seg)
        elif name.startswith('tile1_impassable'):
            self.tile1_by_type[NavType.IMPASSABLE].append(seg)
        elif name.startswith('tile1_impasssable'): # sic
            self.tile1_by_type[NavType.IMPASSABLE].append(seg)
        elif name.startswith('tile1_swervible'): # sic
            self.tile1_by_type[NavType.SWERVIBLE].append(seg)
        elif name.startswith('tile1_passable_tunnel'):
            self.tile1_by_type[NavType.TUNNEL].append(seg)
        elif name.startswith('tile1_passable'):
            self.tile1_by_type[NavType.PASSABLE].append(seg)
        elif name.startswith('tile3_empty'):
            self.tile3_by_type[NavType.EMPTY].append(seg)
        elif name.startswith('tile3_impassable'):
            self.tile3_by_type[NavType.IMPASSABLE].append(seg)
        elif name.startswith('tile3_swervible'): # sic
            self.tile3_by_type[NavType.SWERVIBLE].append(seg)
        elif name.startswith('tile3_swirvible'): # double-sic
            self.tile3_by_type[NavType.SWERVIBLE].append(seg)
        elif name.startswith('tile3_passable_tunnel'):
            self.tile3_by_type[NavType.TUNNEL].append(seg)
        elif name.startswith('tile3_passable'):
            self.tile3_by_type[NavType.PASSABLE].append(seg)


def should_cull_collision_poly(name, solid):
    if abs(solid.normal.z) > 0.7 or solid.normal.y > 0.2:
        # not facing towards front
        return True

    lowest_z = 100.0
    highest_z = -100.0
    for point in solid.points:
        if point.z < lowest_z:
            lowest_z = point.z
        if point.z > highest_z:
            highest_z = point.z

    if 'trench3_middle' in name and (lowest_z > -2 or highest_z <= -3):
        return True

    if 'trench' not in name and (lowest_z > 0.5 or highest_z <= 0):
        return True

    return False


shader = Shader.load(Shader.SL_GLSL, "assets/glsl/tube.vert", "assets/glsl/tube.frag")


class Ring:
    def __init__(self):
        self.collision_nodes = []
        self.r_to_x = 1
        self.next_ring = None
        self.start_depth = 0.0
        self.end_depth = 0.0
        self.exits = [] # i, sw_left, sw_right

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
    def __init__(self, seed=2):
        self.root = NodePath("root")
        self.root.set_shader(shader)
        self.root.node().set_final(True)
        self.root.node().set_bounds(OmniBoundingVolume())
        self.branch_root = self.root.attach_new_node("trunk")
        self.branch_root.set_shader_inputs(start_center=(0, 0), end_center=(0, 0))
        self.random = Random(seed)
        self.y = 0
        self.counter = 0
        self.first_ring = None
        self.last_ring = None

        self.ts_steel = TileSet()
        self.ts_rift = TileSet()
        self.ts_flesh = TileSet()
        self.ts_level = getattr(self, 'ts_' + LEVEL)

        model = loader.load_model('assets/bam/segments/segments.bam')

        print("Processing segments...")
        for n in model.children:
            name = n.name
            if name.startswith("steel_"):
                self.ts_steel.add(n)
            elif name.startswith("rift_"):
                self.ts_rift.add(n)
            elif name.startswith("flesh_"):
                self.ts_flesh.add(n)
        print("Done.")

        self.seg_count = 20
        self.next_emptyish = False
        self.generator = iter(self.gen_tube(LEVEL))
        self.last_ring = next(self.generator)
        self.first_ring = self.last_ring
        self.current_ring = self.first_ring

        for i in range(NUM_RINGS):
            if self.last_ring.branch_root == self.branch_root:
                next(self.generator)

    def calc_types(self, count, allow_swervible, allow_passable=True, allow_tunnel=True):
        exits = self.last_ring.exits
        old_count = len(self.last_ring.collision_nodes)
        if count > old_count and count / old_count == 3:
            exits = [(exit[0] * 3, exit[1], exit[2]) for exit in exits]
        elif count != old_count:
            if allow_tunnel and allow_passable:
                return RingList(self.random.choices((NavType.PASSABLE, NavType.PASSABLE, NavType.TUNNEL)) * count)
            elif allow_tunnel:
                return RingList([NavType.TUNNEL] * count)
            else:
                return RingList([NavType.PASSABLE] * count)

        # Slight chance of random passable tile
        #types = RingList(self.random.choices((NavType.IMPASSABLE, NavType.IMPASSABLE, NavType.IMPASSABLE, NavType.IMPASSABLE, NavType.PASSABLE)) * count)
        types = RingList(self.random.choices((NavType.IMPASSABLE, NavType.IMPASSABLE, NavType.IMPASSABLE, NavType.IMPASSABLE, NavType.PASSABLE if allow_passable else NavType.TUNNEL)) * count)

        for i, sw_left, sw_right in exits:
            if types[i].is_passable:
                continue

            sw_next = (types[i] == NavType.SWERVIBLE)

            if (sw_next or sw_left) and types[i - 1] in (NavType.PASSABLE, NavType.EMPTY):
                continue

            if (sw_next or sw_right) and types[i + 1] in (NavType.PASSABLE, NavType.EMPTY):
                continue

            if sw_left and types[i - 1] == NavType.TUNNEL:
                continue

            if sw_right and types[i + 1] == NavType.TUNNEL:
                continue

            if sw_left >= 2 and types[i - 2] in (NavType.PASSABLE, NavType.EMPTY):
                continue

            if sw_right >= 2 and types[i + 2] in (NavType.PASSABLE, NavType.EMPTY):
                continue

            if sw_left and sw_next and types[i - 1] == NavType.SWERVIBLE and types[i - 2] in (NavType.PASSABLE, NavType.EMPTY):
                continue

            if sw_right and sw_next and types[i + 1] == NavType.SWERVIBLE and types[i + 2] in (NavType.PASSABLE, NavType.EMPTY):
                continue

            choices = []
            if allow_swervible or allow_passable or sw_left:
                choices.append(-1)
            if allow_swervible or allow_passable or sw_right:
                choices.append(1)
            if sw_left and (allow_swervible or allow_passable):
                choices.append(-2)
            if sw_right and (allow_swervible or allow_passable):
                choices.append(2)

            choice = self.random.choice(choices) if choices else 0

            if (choice < 0 and not sw_left) or (choice > 0 and not sw_right):
                # To get to this one, need to swerve through the tile ahead
                assert allow_swervible or allow_passable
                if allow_swervible and types[i] != NavType.PASSABLE and types[i] != NavType.EMPTY:
                    types[i] = NavType.SWERVIBLE
                else:
                    # we just have to make this one passable
                    if types[i] != NavType.EMPTY:
                        types[i] = NavType.PASSABLE
                    continue
                types[i + choice] = NavType.PASSABLE
            else:
                assert allow_tunnel or allow_passable
                if allow_tunnel:
                    types[i + choice] = NavType.TUNNEL
                elif allow_passable:
                    types[i + choice] = NavType.PASSABLE
                else:
                    types[i + choice] = NavType.EMPTY

            if abs(choice) == 2:
                # To get to this one, the one between it must also be swervible
                assert allow_swervible or allow_passable
                assert types[i + choice // 2] != NavType.TUNNEL
                types[i + choice // 2] = NavType.SWERVIBLE

        return types

    @property
    def next_ring(self):
        ring = self.current_ring
        if ring.next_ring is None:
            return next(self.generator)
        return ring.next_ring

    def update(self, dt):
        dy = dt * SPEED
        self.y += dy

        if self.y == dy:
            dy = 0

        self.root.set_shader_input('y', self.y)

        self.first_ring.advance(dy)

        ring = self.first_ring
        while ring is not None:
            if ring.node_path.get_y() > -Y_SPACING / 2.0:
                self.current_ring = ring
                if self.branch_root != ring.branch_root:
                    self.branch_root.remove_node()
                    self.branch_root = ring.branch_root
                    self.branch_root.set_shader_inputs(start_center=(0, 0), end_center=(0, 0))
                break
            ring = ring.next_ring

        ring = self.first_ring
        while ring and ring.needs_cull():
            ring.node_path.remove_node()
            ring = ring.next_ring
            self.first_ring = ring

        # Make sure we have NUM_RINGS.
        ring = self.first_ring
        for i in range(NUM_RINGS):
            if ring.branch_root != self.branch_root:
                break

            ring = ring.next_ring
            if not ring:
                ring = next(self.generator)

    def gen_tube(self, level):
        if level == 'steel':
            yield from self.gen_steel_level()

        if level != 'flesh':
            yield from self.gen_rift_level()

        yield from self.gen_flesh_level()

    def gen_steel_level(self):
        self.seg_count = 2
        self.ts_level = self.ts_steel
        yield self.gen_empty_ring(delta=18)

        yield self.gen_empty_ring(delta=10)
        yield from self.gen_tile_section(3)
        yield from self.gen_trench()
        yield self.gen_passable_ring(delta=30)
        yield self.gen_empty_ring(delta=60)
        yield self.gen_passable_ring(delta=30)
        yield from self.gen_tile_section(3)
        yield from self.gen_tile_section(1)
        yield from self.gen_trench()

    def gen_rift_level(self):
        self.ts_level = self.ts_rift
        yield self.gen_empty_ring()

    def gen_flesh_level(self):
        # Always start with empty
        self.seg_count = 6
        yield self.gen_empty_ring(ts=self.ts_rift)

        ts = self.ts_flesh
        self.ts_level = ts

        # mouth... ewww
        self.seg_count = 200
        #yield self.gen_empty_ring()
        yield self.gen_ring([ts.segments[seg] for seg in ts.segments if 'obstacle' in seg and 'tile1' in seg] * 100)
        yield self.gen_ring([ts.segments[seg] for seg in ts.segments if 'obstacle' in seg and 'tile1' in seg] * 40)
        yield self.gen_ring([ts.segments[seg] for seg in ts.segments if 'obstacle' in seg and 'tile1' in seg] * 15)
        yield self.gen_ring([ts.segments[seg] for seg in ts.segments if 'obstacle' in seg and 'tile1' in seg] * 6)
        yield self.gen_ring([ts.segments[seg] for seg in ts.segments if 'obstacle' in seg and 'tile1' in seg] * 3)

        ring = self.last_ring
        ring.exits.append((self.random.randrange(0, 3), 0, 0))

        #yield from self.gen_tile_section()
        #yield from self.gen_tile_section()

        # stomach or something ew
        ring = self.gen_empty_ring(delta=-self.seg_count + 3)
        ring.node_path.set_shader_input("radius", (ring.start_radius, 1))
        yield ring
        self.seg_count = 40
        yield self.gen_empty_ring()
        yield self.gen_passable_ring()
        yield from self.gen_tile_section()
        yield from self.gen_tile_section()
        yield self.gen_passable_ring(delta=-3)
        yield from self.gen_transition(6)
        yield from self.gen_tile_section()
        yield from self.gen_tile_section()
        yield self.gen_passable_ring(delta=3)
        yield from self.gen_tile_section()
        yield from self.gen_tile_section()
        yield self.gen_passable_ring(delta=3)
        yield from self.gen_tile_section()
        yield from self.gen_tile_section()
        yield self.gen_passable_ring(delta=-3)

        while True:
            yield self.gen_empty_ring()
            yield from self.gen_tile_section()
            yield self.gen_empty_ring()
            yield from self.gen_trench()
            yield self.gen_empty_ring()

    def gen_transition(self, to_segs, ts=None):
        ts = ts or self.ts_level

        types = self.calc_types(self.seg_count, allow_swervible=False, allow_passable=False, allow_tunnel=True)
        ring = self.gen_ring([ts.segments['tile1_transition_impassable'] if nt == NavType.IMPASSABLE else ts.segments['tile1_transition'] for nt in types])
        ring.end_depth = 3.0
        yield ring

        branch_root = NodePath('branch')

        rad = (to_segs - len(types)) / AR_FACTOR - 3
        fac = tau / self.seg_count
        for seg in range(self.seg_count):
            if types[seg].is_passable:
                center = Vec2(-sin(seg * fac), cos(seg * fac)) * rad
                inst = self.root.attach_new_node('inst')
                branch_root.instance_to(inst)
                inst.set_shader_inputs(start_center=center, end_center=center)

        self.seg_count = to_segs

        # Every tile after tunnel should be passable but not a tunnel
        options = [ts.segments[seg] for seg in ts.segments if 'passable_gate' in seg or 'passable_obstacle' in seg]
        segs = self.random.choices(options, k=to_segs)
        ring = self.gen_ring(segs, branch_root=branch_root)

        for i in range(to_segs):
            ring.exits.append((i, 1, 1))

        yield ring

    def gen_tile_section(self, width=None, ts=None):
        if width is None:
            width = self.random.choice((1, 3))

        ts = self.ts_level

        if len(ts.tile1_by_type[NavType.PASSABLE]) == 0:
            width = 3

        count = int(ceil(self.seg_count / width))

        tiles = ts.tile3_by_type if width == 3 else ts.tile1_by_type
        allow_tunnel = len(tiles[NavType.TUNNEL]) > 0

        for j in range(SECTION_LENGTH):
            types = self.calc_types(count, allow_swervible=True, allow_tunnel=allow_tunnel)
            segs = RingList(self.random.choice(tiles[next_type]) for next_type in types)

            ring = self.gen_ring(segs, width=width)
            ring.exits = []
            for i in range(count):
                if types[i] == NavType.TUNNEL:
                    # Can't swerve out of a tunnel
                    ring.exits.append((i, 0, 0))
                elif types[i] == NavType.PASSABLE:
                    ring.exits.append((i, types[i - 1] == NavType.PASSABLE, types[i + 1] == NavType.PASSABLE))
            yield ring

    def gen_passable_ring(self, delta=0, ts=None):
        ts = ts or self.ts_level

        tiles = ts.tile1_by_type[NavType.PASSABLE]
        width = 1
        if not tiles:
            tiles = ts.tile3_by_type[NavType.PASSABLE]
            width = 3

        segs = self.random.choices(tiles, k=int(ceil((self.seg_count + delta) / width)))
        ring = self.gen_ring(segs)

        for i in range(len(segs)):
            ring.exits.append((i, 1, 1))

        return ring

    def gen_empty_ring(self, delta=0, ts=None):
        ts = ts or self.ts_level

        if ts.tile1_by_type[NavType.EMPTY]:
            segs = self.random.choices(ts.tile1_by_type[NavType.EMPTY], k=max(1, self.seg_count + delta))
        else:
            segs = self.random.choices(ts.tile3_by_type[NavType.EMPTY], k=int(ceil((self.seg_count + delta) / 3)))

        ring = self.gen_ring(segs)

        for i in range(len(segs)):
            ring.exits.append((i, 2, 2))

        return ring

    def gen_trench(self, ts=None):
        ts = ts or self.ts_level

        if not ts.entrance_trenches or not ts.middle_trenches:
            return

        types = self.calc_types(self.seg_count // 3, allow_swervible=False, allow_passable=False, allow_tunnel=True)
        exits = []
        for i in range(len(types)):
            if types[i] == NavType.TUNNEL:
                exits.append((i, 0, 0))

        segs = [self.random.choice(ts.entrance_trenches if nt == NavType.TUNNEL else ts.impassable_trenches) for nt in types]
        ring = self.gen_ring(segs, width=3)
        ring.exits = exits
        ring.end_depth = TRENCH_DEPTH
        yield ring

        for i in range(SECTION_LENGTH):
            segs = [self.random.choice(ts.middle_trenches if nt == NavType.TUNNEL else ts.impassable_trenches) for nt in types]
            ring = self.gen_ring(segs, width=3)
            ring.exits = exits
            ring.start_depth = TRENCH_DEPTH
            ring.end_depth = TRENCH_DEPTH
            yield ring

        if ts.exit_trenches:
            segs = [self.random.choice(ts.exit_trenches if nt == NavType.TUNNEL else ts.impassable_trenches) for nt in types]
            ring = self.gen_ring(segs, width=3)
            ring.exits = exits
            ring.start_depth = TRENCH_DEPTH
            yield ring

    def gen_ring(self, set, width=1, parent=None, branch_root=None):
        count = len(set) * width
        from_radius = self.seg_count / AR_FACTOR
        to_radius = count / AR_FACTOR

        if parent is None:
            parent = self.last_ring

        if branch_root is None:
            branch_root = self.last_ring.branch_root if self.last_ring else self.branch_root

        ring = Ring()
        ring.num_segments = count
        ring.start_radius = from_radius
        ring.end_radius = to_radius
        ring.x_spacing = X_SPACING * width
        ring.branch_root = branch_root

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
        np.set_y(parent.node_path.get_y() + Y_SPACING if parent else 0)
        np.reparent_to(ring.branch_root)

        if parent is not None:
            parent.next_ring = ring
        if parent is self.last_ring:
            self.last_ring = ring

        self.counter += 1
        self.seg_count = count
        return ring
