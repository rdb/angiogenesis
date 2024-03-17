from panda3d.core import NodePath, Shader, OmniBoundingVolume

from random import Random


NUM_RINGS = 60
X_SPACING = 2
Y_SPACING = 10
SPEED = 10
AR_FACTOR = 2

SEQ_LENGTH = 10


shader = Shader.load(Shader.SL_GLSL, "assets/glsl/tube.vert", "assets/glsl/tube.frag")


class Ring:
    def __init__(self):
        self.is_trench = False

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
        is_trench = self.random.choice((True, False))
        for i in range(SEQ_LENGTH):
            self.gen_ring(self.next_radius, is_trench)

        self.next_radius += 2

    def gen_ring(self, radius, is_trench):
        count = int(radius * AR_FACTOR + 0.5)

        if is_trench:
            radius += 1

        ring = Ring()
        ring.num_segments = count
        ring.start_radius = radius
        ring.end_radius = radius

        np = NodePath("ring")
        np.set_shader_input("num_segments", count)
        np.set_shader_input("radius", radius)
        np.node().set_final(True)
        ring.node_path = np

        # for count = 4
        for c in range(count):
            if is_trench:
                seg = self.random.choice(self.trenches)
            else:
                seg = self.random.choice(self.tiles)
            seg = seg.copy_to(np)
            seg.set_pos(c * X_SPACING, 0, 0)

        np.flatten_strong()
        np.set_y(self.counter * Y_SPACING - self.y)
        np.reparent_to(self.root)
        self.rings.append(ring)
        self.counter += 1
        return np
