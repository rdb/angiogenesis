from panda3d.core import NodePath, Shader, OmniBoundingVolume

from random import Random


NUM_RINGS = 60
X_SPACING = 2
Y_SPACING = 10
SPEED = 10
AR_FACTOR = 2


shader = Shader.load(Shader.SL_GLSL, "assets/glsl/tube.vert", "assets/glsl/tube.frag")


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

        self.radius = 4

        model = loader.load_model('assets/bam/segments.bam')
        self.trenches = model.find_all_matches('trench_*')
        self.tiles = model.find_all_matches('tile_*')

        for i in range(NUM_RINGS):
            np = self.gen_ring()

        taskMgr.add(self.task)

    def task(self, task):
        y = task.time * SPEED
        if self.y == 0:
            dy = 0
        else:
            dy = y - self.y

        self.y = y

        self.root.set_shader_input('y', self.y)

        for i, ring in enumerate(self.rings):
            new_y = ring.get_y() - dy
            ring.set_y(new_y)

        while self.rings and self.rings[0].get_y() < -Y_SPACING:
            ring = self.rings.pop(0)
            ring.remove_node()
            ring = self.gen_ring()

        return task.cont

    def gen_ring(self):
        is_trench = self.random.choice((True, False))

        count = int(self.radius * AR_FACTOR + 0.5)

        np = NodePath("ring")
        np.set_shader_input("num_segments", count)
        np.set_shader_input("radius", self.radius)
        np.node().set_final(True)

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
        self.rings.append(np)
        self.counter += 1
        return np
