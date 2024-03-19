from panda3d.core import NodePath

from direct.showbase.DirectObject import DirectObject


CAM_TRAIL = 1.5 # units
CAM_Z_OFFSET = 0.2
ROT_ACC = -500
ROT_SPEED_LIMIT = 500
ROT_BRAKE = 0.01

SHIP_ROLL_ANGLE = 45
SHIP_ROLL_SPEED = 0.0000001
SHIP_DONK_FACTOR = 100


def smoothstep(x):
    x = max(0, min(x, 1))
    return x * x * (3 - 2 * x)


class Ship:
    def __init__(self):
        self.root = NodePath("dummy")
        self.ship = loader.load_model("assets/bam/ship/ship.bam")
        #self.ship.set_hpr(90, 90, 90)
        self.ship.set_scale(0.05)
        self.ship.flatten_strong()
        self.ship.reparent_to(self.root)


class ShipControls(DirectObject):
    def __init__(self, ship, tube):
        self.ship = ship
        self.tube = tube
        base.taskMgr.add(self.move, sort=2)
        base.taskMgr.add(self.cam_move, sort=4)

        self.cam_root = NodePath("dummy")
        self.cam_root.reparent_to(render)
        base.camera.reparent_to(self.cam_root)
        self.ship.ship.set_pos(0, 0, 0.1 - tube.radius)
        base.camera.set_pos(0, 0 - CAM_TRAIL, self.ship.ship.get_z() + CAM_Z_OFFSET)

        self.r_speed = 0

        self.z_origin = 0.1 - tube.radius
        self.z_target = 0.1 - tube.radius
        self.z_t = 1.0

        self.trail = [(0, 0, base.camera.get_z())]

    def set_ship_z_target(self, z):
        if z != self.z_target:
            self.z_origin = self.ship.ship.get_z()
            self.z_t = 0.0
            self.z_target = z

    def donk(self, deflect):
        self.ship.root.set_r(self.ship.root.get_r() - deflect * 360)

        if deflect < 0:
            hor = 1
        elif deflect > 0:
            hor = -1
        elif self.r_speed < 0:
            hor = 1
        elif self.r_speed > 0:
            hor = -1
        else:
            hor = 0

        self.r_speed = hor * SHIP_DONK_FACTOR

        self.update_ship_rotation(-hor, force=True)

    def update_ship_rotation(self, hor, force=False):
        target_h = self.r_speed * 60 / ROT_SPEED_LIMIT
        target_r = hor * SHIP_ROLL_ANGLE
        if force:
            t = 0.0
        else:
            t = SHIP_ROLL_SPEED ** base.clock.dt
        self.ship.ship.set_hpr(target_h, 0, target_r * (1 - t) + self.ship.ship.get_r() * t)

    def move(self, task):
        is_down = base.mouseWatcherNode.is_button_down

        current_ring = self.tube.current_ring
        self.set_ship_z_target(0.1 - max(current_ring.start_radius, current_ring.end_radius))

        if self.z_t < 1.0:
            self.z_t = min(1.0, self.z_t + base.clock.dt)
            t = smoothstep(self.z_t)
            z = self.z_origin * (1 - t) + self.z_target * t
        else:
            z = self.z_target

        z = max(z, 0.1 - current_ring.radius_at(0.0))
        self.ship.ship.set_z(z)

        hor = is_down('arrow_right') - is_down('arrow_left')

        if hor != 0:
            self.r_speed += hor * base.clock.dt * ROT_ACC

            if abs(self.r_speed) > ROT_SPEED_LIMIT:
                if self.r_speed > 0:
                    self.r_speed = ROT_SPEED_LIMIT
                else:
                    self.r_speed = -ROT_SPEED_LIMIT
        else:
            self.r_speed *= ROT_BRAKE ** base.clock.dt

        r = self.ship.root.get_r() + self.r_speed * base.clock.dt / -z
        self.ship.root.set_r(r)

        self.update_ship_rotation(hor)

        return task.cont

    def cam_move(self, task):
        # This happens after collisions, so that the camera doesn't clip
        r = self.ship.root.get_r()
        z = self.ship.ship.get_z()
        self.trail.append((self.tube.y, r, z))

        # Calculate ship r 3 seconds ago
        while len(self.trail) > 2 and self.trail[1][0] < self.tube.y - CAM_TRAIL:
            self.trail.pop(0)

        y0, r0, z0 = self.trail[0]
        y1, r1, z1 = self.trail[1]
        if y0 == y1:
            r = r0
            z = z0
        else:
            yt = (self.tube.y - CAM_TRAIL - y0) / (y1 - y0)
            r = r0 * (1 - yt) + r1 * yt
            z = z0 * (1 - yt) + z1 * yt

        self.cam_root.set_r(r)
        base.camera.set_z(z + CAM_Z_OFFSET)
        #base.camera.look_at(self.ship.ship)

        return task.cont
