from panda3d.core import NodePath

from direct.showbase.DirectObject import DirectObject


TRAIL_LENGTH = 10
ROT_ACC = -300
ROT_BRAKE = 0.0001


def smoothstep(x):
    x = max(0, min(x, 1))
    return x * x * (3 - 2 * x)


class Ship:
    def __init__(self):
        self.root = NodePath("dummy")
        self.ship = loader.load_model("assets/bam/ship.bam")
        #self.ship.set_hpr(90, 90, 90)
        self.ship.set_scale(0.05)
        self.ship.flatten_strong()
        self.ship.reparent_to(self.root)


class ShipControls(DirectObject):
    def __init__(self, ship, tube):
        self.ship = ship
        self.tube = tube
        base.taskMgr.add(self.move)

        self.cam_root = NodePath("dummy")
        self.cam_root.reparent_to(render)
        base.camera.reparent_to(self.cam_root)
        base.camera.set_pos(-0.1, -1.5, 0.3 - tube.radius)
        self.ship.ship.set_pos(0, 0, 0.1 - tube.radius)

        self.r_speed = 0

        self.z_origin = 0.3 - tube.radius
        self.z_target = 0.3 - tube.radius
        self.z_t = 1.0

        self.trail = [0]
        self.last_sample = 0

    def set_cam_z_target(self, z):
        if z != self.z_target:
            self.z_origin = base.camera.get_z()
            self.z_t = 0.0
            self.z_target = z

    def move(self, task):
        is_down = base.mouseWatcherNode.is_button_down

        #if self.tube.rings[1].children[0].name.startswith('trench'):
        #    self.set_cam_z_target(0.3 - self.tube.radius)
        #else:
        #    self.set_cam_z_target(0.3 - self.tube.radius)

        if self.z_t < 1.0:
            self.z_t = min(1.0, self.z_t + base.clock.dt)
            t = smoothstep(self.z_t)
            base.camera.set_z(self.z_origin * (1 - t) + self.z_target * t)

        hor = is_down('arrow_right') - is_down('arrow_left')

        if hor != 0:
            self.r_speed += hor * base.clock.dt * ROT_ACC
        else:
            self.r_speed *= ROT_BRAKE ** base.clock.dt

        r = self.ship.root.get_r() + self.r_speed * base.clock.dt
        self.ship.root.set_r(r)

        while self.last_sample < task.time:
            self.trail.append(r)
            self.last_sample += 0.01

        if len(self.trail) > TRAIL_LENGTH:
            self.trail = self.trail[-TRAIL_LENGTH:]
            cam_r = self.trail[0]
            self.cam_root.set_r(cam_r)

        #base.camera.look_at(self.ship.ship)

        return task.cont
