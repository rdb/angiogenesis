from panda3d.core import NodePath
from panda3d.core import Point3, Vec4

from direct.showbase.DirectObject import DirectObject
from direct.interval.IntervalGlobal import Sequence, Func
from direct.motiontrail.MotionTrail import MotionTrail
from direct.gui.OnscreenText import OnscreenText
from random import random


CAM_TRAIL = 1.5 # units
CAM_Z_OFFSET = 0.2
ROT_ACC = -700
ROT_SPEED_LIMIT = 500
ROT_BRAKE = 0.01

SHIP_ROLL_ANGLE = 45
SHIP_ROLL_SPEED = 0.01
SHIP_DONK_FACTOR = 100

SHIP_HEIGHT = 0.2

USE_GRAVITY = True
SHIP_Z_ACC = 0.7
SHIP_BOUNCE = 0.1


def smoothstep(x):
    x = max(0, min(x, 1))
    return x * x * (3 - 2 * x)


class ShipTrail:
    def __init__(self, root, ship):
        self.ship = ship
        self.trail = MotionTrail("ship", self.ship)

        taskMgr.remove(self.trail.motion_trail_task_name)
        self.trail.time_window = 0.1 # Length of trail
        self.trail.resolution_distance = 0.001
        self.trail.register_motion_trail()
        self.trail.geom_node_path.reparent_to(render)
        for v, pc in enumerate((
            (Point3(-0.10, -0.00, -0.05),Vec4(1,0,1,0)),
            (Point3(-0.08, -0.00, -0.05),Vec4(1,0,1,1)),
            (Point3(-0.06, -0.00, -0.05),Vec4(1,0,1,0)),
            (Point3(-0.00, -0.00, -0.05),Vec4(1,0,1,0)),
            (Point3( 0.06, -0.00, -0.05),Vec4(1,0,1,0)),
            (Point3( 0.08, -0.00, -0.05),Vec4(1,0,1,1)),
            (Point3( 0.100,-0.00, -0.05),Vec4(1,0,1,0)),
        )):
            pos, col = pc
            self.trail.add_vertex(pos)
            self.trail.set_vertex_color(v, col, col)
        self.trail.update_vertices()

    def update(self, tube_y):
        mt = MotionTrail.motion_trail_list[0]
        transform = self.ship.getNetTransform().getMat()
        transform = transform * transform.translate_mat(0,tube_y,0)
        self.trail.geom_node_path.set_y(-tube_y)
        mt.transferVertices()
        mt.cmotion_trail.updateMotionTrail(base.clock.getFrameTime(), transform)


class Ship:
    def __init__(self):
        self.root = NodePath("dummy")
        self.ship = loader.load_model("assets/bam/ship/ship.bam")
        self.trail = ShipTrail(self.root, self.ship)
        #self.ship.set_hpr(90, 90, 90)
        self.ship.set_scale(0.05)
        self.ship.flatten_strong()
        self.ship.reparent_to(self.root)


class ShipControls(DirectObject):
    def __init__(self, ship, tube):
        self.ship = ship
        self.tube = tube
        base.taskMgr.add(self.cam_move, sort=4)

        ring = tube.first_ring

        self.cam_root = NodePath("dummy")
        self.cam_root.reparent_to(render)
        base.camera.reparent_to(self.cam_root)
        self.ship.ship.set_pos(0, 0, SHIP_HEIGHT - ring.start_radius)
        base.camera.set_pos(0, 0 - CAM_TRAIL, self.ship.ship.get_z() + CAM_Z_OFFSET)

        self.r_speed = 0

        self.z_origin = SHIP_HEIGHT - ring.start_radius
        self.z_target = SHIP_HEIGHT - ring.start_radius
        self.z_t = 1.0
        self.z_speed = 0.0

        self.trail = [(0, 0, base.camera.get_z())]

    def get_ship_z_above_ground(self):
        return self.ship.ship.get_z() + self.tube.current_ring.radius_at(0.0)

    def set_ship_z_target(self, z):
        if z != self.z_target:
            self.z_origin = self.ship.ship.get_z()
            self.z_t = 0.0
            self.z_target = z

    def donk(self, deflect, pain):
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

        if pain > 0.8:
            text = OnscreenText('CRASH!', fg=(1, 1, 1, 1), scale=0.5)
        else:
            text = OnscreenText('donk', fg=(1, 1-pain, 1-pain, 1), scale=0.05)
            text.set_pos(hor * 0.5 + random() - 0.5, 0, random() - 0.5)
        text.set_transparency(1)
        Sequence(text.colorScaleInterval(2.0, (1, 1, 1, 0)), Func(text.destroy)).start()

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

    def update(self, dt):
        is_down = base.mouseWatcherNode.is_button_down

        current_ring = self.tube.current_ring
        #self.set_ship_z_target(SHIP_HEIGHT - max(current_ring.start_radius + current_ring.start_depth, current_ring.end_radius + current_ring.end_depth))
        self.set_ship_z_target(SHIP_HEIGHT - current_ring.radius_at(0.0) - current_ring.depth_at(0.0))

        if USE_GRAVITY:
            z = self.ship.ship.get_z()
            if z > self.z_target:
                self.z_speed -= SHIP_Z_ACC * dt
                z += self.z_speed * dt

            if z < self.z_target:
                if abs(self.z_speed) < 0.1:
                    self.z_speed = 0
                    z = self.z_target
                elif self.z_speed < 0:
                    text = OnscreenText('splish', fg=(1, 1, 0, 1), scale=0.05)
                    text.set_pos(random() - 0.5, 0, random() - 1.0)
                    text.set_transparency(1)
                    Sequence(text.colorScaleInterval(2.0, (1, 1, 1, 0)), Func(text.destroy)).start()
                    z = self.z_target
                    self.z_speed = -self.z_speed * SHIP_BOUNCE
                else:
                    self.z_speed += SHIP_Z_ACC * dt
                z += self.z_speed * dt
                if z < self.z_target:
                    z = self.z_target
                    self.z_speed = 0

        elif self.z_t < 1.0:
            self.z_t = min(1.0, self.z_t + dt)
            t = smoothstep(self.z_t)
            z = self.z_origin * (1 - t) + self.z_target * t
        else:
            z = self.z_target

        #z = max(z, self.z_target)
        self.ship.ship.set_z(z)

        hor = is_down('arrow_right') - is_down('arrow_left')

        if hor != 0:
            self.r_speed += hor * dt * ROT_ACC

            if abs(self.r_speed) > ROT_SPEED_LIMIT:
                if self.r_speed > 0:
                    self.r_speed = ROT_SPEED_LIMIT
                else:
                    self.r_speed = -ROT_SPEED_LIMIT
        else:
            self.r_speed *= ROT_BRAKE ** dt

        r = self.ship.root.get_r() + self.r_speed * dt / -z
        self.ship.root.set_r(r)

        self.update_ship_rotation(hor)
        self.ship.trail.update(self.tube.y)

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

        if z > self.ship.ship.get_z() + 0.5:
            z = self.ship.ship.get_z() + 0.5

        if z < self.ship.ship.get_z():
            z = self.ship.ship.get_z()

        #self.cam_root.set_pos(self.ship.root.get_pos())
        self.cam_root.set_r(r)
        base.camera.set_z(z + CAM_Z_OFFSET)
        #base.camera.look_at(self.ship.ship)

        return task.cont
