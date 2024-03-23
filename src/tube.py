from panda3d.core import (
    NodePath,
    Shader,
    ShaderAttrib,
    OmniBoundingVolume,
    NodePathCollection,
    CollisionPolygon,
    Vec2,
)

from random import Random
from math import pi, tau, ceil, cos, sin
from enum import Enum

from .gurgles import MultiTrack
from .util import RingList


LEVEL = 'steel'
LEVELS = 'steel', 'rift', 'flesh'
NUM_RINGS = 30
X_SPACING = 2
Y_SPACING = 40
SPEED = 10
AR_FACTOR = pi
MIN_SEG_COUNT = 6
MAX_SWERVE = 6
CULL_MARGIN = 5.0

SECTION_LENGTH = 3
TRENCH_DEPTH = 2.5


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


class TileSet:
    def __init__(self, name):
        self.name = name
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

        cnps = []
        for num, cnp in enumerate(n.find_all_matches("**/+CollisionNode")):
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

            if self.name == "rift":
                cnp.set_tag("material", "flesh" if num else "steel")
            else:
                cnp.set_tag("material", self.name)

            if num_solids > 0:
                cnps.append(cnp)

        n.clear_transform()
        n.flatten_strong()

        seg = (n, cnps)
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
        self.play_tracks = ()
        self.override_gravity = None

    @property
    def y(self):
        return self.node_path.get_y()

    @y.setter
    def y(self, y):
        self.node_path.set_y(y)

    def radius_at(self, y):
        t = (y - self.node_path.get_y()) / Y_SPACING + 0.5
        #t = max(0, min(1, t))
        return self.end_radius * t + self.start_radius * (1 - t)

    def depth_at(self, y):
        t = (y - self.node_path.get_y()) / Y_SPACING + 0.5
        #t = max(0, min(1, t))
        return self.end_depth * t + self.start_depth * (1 - t)

    def needs_cull(self):
        return self.node_path.get_y() < -Y_SPACING / 2.0 - CULL_MARGIN

    def advance(self, dy):
        new_y = self.node_path.get_y() - dy
        self.node_path.set_y(new_y)
        if self.next_ring:
            self.next_ring.advance(dy)


class Tube:
    def __init__(self, seed=2):
        self.root = NodePath("root")
        self.root.set_shader(shader)
        self.root.set_shader_input('y', 0)
        self.root.node().set_final(True)
        self.root.node().set_bounds(OmniBoundingVolume())
        self.branch_root = self.root.attach_new_node("trunk")
        self.branch_root.set_shader_inputs(start_center=(0, 0), end_center=(0, 0))
        self.random = Random(seed)
        self.y = 0
        self.first_ring = None
        self.last_ring = None
        self.paused = False

        self.music = MultiTrack()
        self.music.load_track('snare', 'assets/music/a/A-snare.mp3')
        self.music.load_track('peace', 'assets/music/a/A-peace.mp3')
        self.music.load_track('medium', 'assets/music/a/A-medium.mp3')
        self.music.load_track('space_big', 'assets/music/a/A-space_big.mp3')
        self.music.load_track('space', 'assets/music/a/A-space.mp3')
        self.music.load_track('tight', 'assets/music/a/A-tight.mp3')
        self.music.load_track('ambient', 'assets/music/b/B-ambient.mp3')
        self.music.load_track('drive', 'assets/music/b/B-drive.mp3')
        self.music.play()

        self.next_level = 'steel'
        self.next_tracks = set()

        self.fog_factor = 0.04
        self.twist_factor = 0.0
        self.bend_time_factor = 0.0
        self.bend_y_factor = 0.0

        self.ts_steel = TileSet('steel')
        self.ts_rift = TileSet('rift')
        self.ts_flesh = TileSet('flesh')
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

        elif old_count > count and old_count / count == 3:
            old_exits = exits
            exits = []
            for old_exit in old_exits:
                i = int(round(old_exit[0] / 3))
                exits.append((i - 1, old_exit[1] + 1, old_exit[2]))
                exits.append((i, old_exit[1], old_exit[2]))
                exits.append((i + 1, old_exit[1], old_exit[2] + 1))

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

    def resume(self):
        self.paused = False

    def pause(self):
        self.paused = True

    def set_y(self, y):
        dy = y - self.y
        self.y = y
        self.root.set_shader_input('y', self.y)
        self.first_ring.advance(dy)
        while self.first_ring.y > -Y_SPACING:
            ring = self.prepend_empty_ring()

    def update(self, dt):
        if self.paused:
            return

        dy = dt * SPEED
        self.y += dy

        if self.y == dy:
            dy = 0

        self.root.set_shader_input('y', self.y)

        self.first_ring.advance(dy)

        ring = self.first_ring
        while ring is not None:
            if ring.y > -Y_SPACING / 2.0:
                self.music.set_playing_tracks(ring.play_tracks)
                self.current_ring = ring
                if self.branch_root != ring.branch_root:
                    ring.inst_parent.remove_node()
                    ring.branch_root.reparent_to(self.root)
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

                # generating one per frame is enough
                break

    def gen_tube(self, level):
        if level == 'steel':
            yield from self.gen_steel_level()

        if level != 'flesh':
            yield from self.gen_rift_level()

        yield from self.gen_flesh_level()

    def gen_steel_level(self):
        self.fog_factor = 0.008
        self.twist_factor = 0.0
        self.bend_time_factor = 0.0
        self.bend_y_factor = 0.0002
        self.next_level = 'steel'

        self.seg_count = 60
        self.ts_level = self.ts_steel
        self.next_tracks = set(['peace'])
        yield self.gen_empty_ring()
        yield from self.gen_obstacle_section()
        yield from self.gen_wall_section(2)
        yield from self.gen_tile_section(1)

        yield from self.gen_trench()
        self.next_tracks.add('peace')

        yield self.gen_empty_ring(delta=10)
        yield from self.gen_random_section()

        self.next_tracks.add('space_big')
        yield self.gen_empty_ring(delta=30)
        yield self.gen_empty_ring(delta=60)
        yield self.gen_empty_ring(delta=30)
        yield from self.gen_random_section()
        yield from self.gen_tile_section(3)
        yield from self.gen_random_section()
        yield from self.gen_random_section()
        yield from self.gen_trench()
        yield from self.gen_tile_section(1)
        self.next_tracks.discard('space_big')
        yield self.gen_passable_ring()
        self.next_tracks.discard('peace')

        self.next_tracks.add('tight')
        yield from self.gen_transition(6)
        yield from self.gen_wall_section()

    def gen_rift_level(self):
        self.fog_factor = 0.008
        self.twist_factor = 0.0
        self.bend_time_factor = 0.0
        self.bend_y_factor = 0.0002
        self.next_level = 'rift'

        self.seg_count = 6
        self.ts_level = self.ts_rift
        self.next_tracks = set(['tight', 'medium'])
        yield self.gen_empty_ring(delta=10)

        yield self.gen_passable_ring(delta=3)
        yield self.gen_passable_ring(delta=3)
        yield self.gen_passable_ring(delta=3)
        yield self.gen_passable_ring(delta=3)
        yield self.gen_passable_ring(delta=3)
        yield self.gen_passable_ring(delta=3)

        yield from self.gen_trench()

        self.next_tracks = set(['peace', 'drive'])

        self.next_tracks.add('space_big')
        yield self.gen_empty_ring(delta=30)
        yield self.gen_empty_ring(delta=60)
        yield self.gen_empty_ring(delta=30)
        yield from self.gen_tile_section(3)
        yield from self.gen_tile_section(1)
        yield self.gen_empty_ring(delta=3)
        yield from self.gen_trench(length=10)
        self.next_tracks.discard('space_big')
        yield self.gen_empty_ring()
        self.next_tracks.discard('peace')

        self.next_tracks.add('tight')
        yield from self.gen_transition(12)
        yield from self.gen_tile_section(1)
        yield from self.gen_tile_section()
        yield from self.gen_tile_section()

    def gen_flesh_level(self):
        # Always start with empty
        self.next_level = 'flesh'
        self.seg_count = 6
        yield self.gen_empty_ring(ts=self.ts_rift)

        self.next_tracks.discard('tight')
        self.next_tracks.add('space')
        self.next_tracks.add('drive')

        self.fog_factor = 0.04
        self.twist_factor = 5.0
        self.bend_time_factor = 0.0003
        self.bend_y_factor = 0.0002

        ts = self.ts_flesh
        self.ts_level = ts

        # mouth... ewww
        self.seg_count = 200
        #yield self.gen_empty_ring()
        gravity = 0.7
        yield self.gen_ring([ts.segments[seg] for seg in ts.segments if 'obstacle' in seg and 'tile1' in seg] * 100, override_gravity=gravity)
        yield self.gen_ring([ts.segments[seg] for seg in ts.segments if 'obstacle' in seg and 'tile1' in seg] * 40, override_gravity=gravity)
        yield self.gen_ring([ts.segments[seg] for seg in ts.segments if 'obstacle' in seg and 'tile1' in seg] * 15, override_gravity=gravity)
        yield self.gen_ring([ts.segments[seg] for seg in ts.segments if 'obstacle' in seg and 'tile1' in seg] * 6, override_gravity=gravity)
        yield self.gen_ring([ts.segments[seg] for seg in ts.segments if 'obstacle' in seg and 'tile1' in seg] * 3, override_gravity=gravity)

        self.next_tracks.discard('space')
        self.next_tracks.discard('drive')
        self.next_tracks.add('ambient')

        ring = self.last_ring
        ring.exits.append((self.random.randrange(0, 3), 0, 0))

        #yield from self.gen_tile_section()
        #yield from self.gen_tile_section()

        # stomach or something ew
        ring = self.gen_empty_ring(delta=-self.seg_count + 3, override_gravity=1)
        ring.node_path.set_shader_input("radius", (ring.start_radius, 1))
        yield ring
        self.seg_count = 40
        yield self.gen_empty_ring(override_gravity=1)
        yield self.gen_passable_ring(override_gravity=1)
        yield from self.gen_tile_section()
        yield from self.gen_tile_section()
        yield self.gen_passable_ring(delta=-3)
        self.next_tracks.add('drive')
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
        transition_ts = self.ts_steel if ts is self.ts_rift else ts

        types = self.calc_types(self.seg_count, allow_swervible=False, allow_passable=False, allow_tunnel=True)
        ring = self.gen_ring([transition_ts.segments['tile1_transition_impassable'] if nt == NavType.IMPASSABLE else transition_ts.segments['tile1_transition'] for nt in types])
        ring.end_depth = 3.0
        yield ring

        self.extend_ring_geometry(ring, NUM_RINGS, skip=1, ts=ts)

        inst_parent = self.root.attach_new_node('branch')
        branch_root = NodePath('branch')

        rad = (to_segs - len(types)) / AR_FACTOR - 3
        fac = tau / self.seg_count
        for seg in range(self.seg_count):
            if types[seg].is_passable:
                center = Vec2(-sin(seg * fac), cos(seg * fac)) * rad
                inst = inst_parent.attach_new_node('inst')
                branch_root.instance_to(inst)
                inst.set_shader_inputs(start_center=center, end_center=center)

        self.seg_count = to_segs

        # Every tile after tunnel should be passable but not a tunnel
        options = [transition_ts.segments[seg] for seg in transition_ts.segments if 'tile1_passable_gate' in seg or 'tile1_passable_obstacle' in seg]
        segs = self.random.choices(options, k=to_segs)
        ring = self.gen_ring(segs, inst_parent=inst_parent, branch_root=branch_root)

        for i in range(to_segs):
            ring.exits.append((i, 1, 1))

        yield ring

    def gen_random_section(self):
        width = self.random.choice(('wall', 'obstacle', 1, 3))
        if width == 'wall':
            yield from self.gen_wall_section()
        elif width == 'obstacle':
            yield from self.gen_obstacle_section()
        else:
            yield from self.gen_tile_section(width)

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

    def gen_obstacle_section(self, length=SECTION_LENGTH, ts=None):
        ts = ts or self.ts_level
        count = self.seg_count

        for j in range(length):
            types = self.calc_types(count, allow_swervible=True, allow_tunnel=False)

            exits = []
            segs = RingList()
            for i, nt in enumerate(types):
                if nt == NavType.IMPASSABLE or nt == NavType.SWERVIBLE:
                    segs.append(ts.segments[self.random.choice(('tile1_passable_obstacle_3', 'tile1_passable_obstacle_4'))])
                else:
                    segs.append(ts.segments[self.random.choice(('tile1_empty', 'tile1_empty.001'))])
                    exits.append((i, 2, 2))

            ring = self.gen_ring(segs)
            ring.exits = exits
            yield ring

    def gen_wall_section(self, length=SECTION_LENGTH, ts=None):
        ts = ts or self.ts_level
        count = self.seg_count

        for j in range(length):
            types = self.calc_types(count, allow_swervible=True, allow_tunnel=False)

            exits = []
            segs = RingList()
            for i, nt in enumerate(types):
                if nt == NavType.IMPASSABLE or nt == NavType.SWERVIBLE:
                    segs.append(ts.segments['tile1_swervible_wall_1'])
                elif nt == NavType.EMPTY or self.random.getrandbits(1):
                    segs.append(ts.segments['tile1_empty'])
                    exits.append((i, 4, 4))
                else:
                    segs.append(ts.segments['tile1_passable_gate_1'])
                    exits.append((i, 4, 4))

            ring = self.gen_ring(segs)
            ring.exits = exits
            yield ring

    def gen_passable_ring(self, delta=0, ts=None, override_gravity=None):
        ts = ts or self.ts_level

        tiles = ts.tile1_by_type[NavType.PASSABLE]
        width = 1
        if not tiles:
            tiles = ts.tile3_by_type[NavType.PASSABLE]
            width = 3

        segs = self.random.choices(tiles, k=int(ceil((self.seg_count + delta) / width)))
        ring = self.gen_ring(segs, width=width, override_gravity=override_gravity)

        for i in range(len(segs)):
            ring.exits.append((i, 1, 1))

        return ring

    def gen_empty_ring(self, delta=0, ts=None, override_gravity=None):
        ts = ts or self.ts_level

        if ts.tile1_by_type[NavType.EMPTY]:
            segs = self.random.choices(ts.tile1_by_type[NavType.EMPTY], k=max(1, self.seg_count + delta))
            width = 1
        else:
            segs = self.random.choices(ts.tile3_by_type[NavType.EMPTY], k=int(ceil((self.seg_count + delta) / 3)))
            width = 3

        ring = self.gen_ring(segs, width=width, override_gravity=override_gravity)

        for i in range(len(segs)):
            ring.exits.append((i, 4, 4))

        return ring

    def gen_trench(self, length=SECTION_LENGTH, ts=None):
        ts = ts or self.ts_level

        if not ts.entrance_trenches or not ts.middle_trenches:
            return

        self.next_tracks.discard('peace')
        self.next_tracks.discard('tight')
        self.next_tracks.add('medium')

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

        for i in range(length):
            segs = [self.random.choice(ts.middle_trenches if nt == NavType.TUNNEL else ts.impassable_trenches) for nt in types]
            ring = self.gen_ring(segs, width=3)
            ring.exits = exits
            ring.start_depth = TRENCH_DEPTH
            ring.end_depth = TRENCH_DEPTH
            yield ring

        self.next_tracks.discard('medium')
        self.next_tracks.add('peace')

        if ts.exit_trenches:
            segs = [self.random.choice(ts.exit_trenches if nt == NavType.TUNNEL else ts.impassable_trenches) for nt in types]
            ring = self.gen_ring(segs, width=3)
            ring.exits = exits
            ring.start_depth = TRENCH_DEPTH
            yield ring

    def gen_ring(self, set, width=1, parent=None, inst_parent=None, branch_root=None, override_gravity=None):
        count = len(set) * width
        assert count > 0

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
        ring.inst_parent = inst_parent
        ring.branch_root = branch_root
        ring.play_tracks = tuple(self.next_tracks)
        ring.level = self.next_level
        ring.override_gravity = override_gravity

        np = NodePath("ring")
        np.node().set_final(True)
        ring.node_path = np

        ring.r_to_x = count * X_SPACING

        for c, (gnode, cnodes) in enumerate(set):
            gnode = gnode.copy_to(np)
            gnode.set_pos(c * X_SPACING * width, 0, 0)
            ring.collision_nodes.append(cnodes)

        np.flatten_strong()
        np.set_y(parent.node_path.get_y() + Y_SPACING if parent else 0)
        np.reparent_to(ring.branch_root)

        np.set_shader_inputs(
            num_segments=count,
            radius=(from_radius, to_radius),
            level_params=(self.fog_factor, self.twist_factor, self.bend_time_factor, self.bend_y_factor),
        )

        if parent is not None:
            parent.next_ring = ring
        if parent is self.last_ring:
            self.last_ring = ring

        self.seg_count = count
        return ring

    def extend_ring_geometry(self, last_ring, num_extra_rings, skip, ts):
        np = last_ring.node_path.attach_new_node("ring_extension")
        width = 1

        for i in range(num_extra_rings):
            segs = self.random.choices([ts.segments[seg] for seg in ts.segments if 'tile1' in seg], k=last_ring.num_segments)

            for c, (gnode, cnodes) in enumerate(segs):
                gnode = gnode.copy_to(np)
                gnode.set_pos(c * X_SPACING * width, (i + skip) * Y_SPACING, 0)

        np.flatten_strong()

    def prepend_empty_ring(self):
        next_ring = self.first_ring
        count = next_ring.num_segments
        radius = next_ring.start_radius + next_ring.start_depth
        level = next_ring.level
        ts = getattr(self, 'ts_' + level)

        if ts.tile1_by_type[NavType.EMPTY]:
            width = 1
            segs = self.random.choices(ts.tile1_by_type[NavType.EMPTY], k=max(1, count))
        else:
            width = 3
            segs = self.random.choices(ts.tile3_by_type[NavType.EMPTY], k=int(ceil((count) / 3)))

        ring = Ring()
        ring.next_ring = next_ring
        ring.num_segments = count
        ring.start_radius = radius
        ring.end_radius = radius
        ring.x_spacing = X_SPACING * width
        ring.inst_parent = next_ring.inst_parent
        ring.branch_root = next_ring.branch_root
        ring.play_tracks = next_ring.play_tracks
        ring.level = level
        ring.override_gravity = False

        np = NodePath("ring")
        np.node().set_final(True)
        ring.node_path = np

        ring.r_to_x = count * X_SPACING

        for c, (gnode, cnodes) in enumerate(segs):
            gnode = gnode.copy_to(np)
            gnode.set_pos(c * X_SPACING * width, 0, 0)
            ring.collision_nodes.append(cnodes)

        np.flatten_strong()
        np.set_y(next_ring.y - Y_SPACING)
        np.reparent_to(ring.branch_root)

        np.set_attrib(next_ring.node_path.get_attrib(ShaderAttrib))
        np.set_shader_inputs(
            num_segments=count,
            radius=(radius, radius),
        )

        self.first_ring = ring
        return ring
