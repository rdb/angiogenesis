from panda3d.core import NodePath, CardMaker, SamplerState
from panda3d.core import ColorBlendAttrib, TransparencyAttrib
from panda3d.core import Point3, Vec4

from direct.showbase.DirectObject import DirectObject
from direct.interval.IntervalGlobal import Sequence, Wait, Func, LerpFunc
from direct.motiontrail.MotionTrail import MotionTrail
from direct.gui.OnscreenText import OnscreenText
from direct.actor.Actor import Actor
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
SHIP_Z_ACC = 2.5
SHIP_BOUNCE = 0.1

REWIND_DIST = 40.0
REWIND_TIME = 1.75
REWIND_WAIT = 2.0

# with higher value, will play big bounce sound only at higher vertical speeds
BOUNCE_LARGE_THRESHOLD = 1.0


def smoothstep(x):
    x = max(0, min(x, 1))
    return x * x * (3 - 2 * x)


class ShipTrail:
    def __init__(self, ship, parent=None):
        self.parent = parent or base.render
        self.ship = ship
        self.trail = MotionTrail("ship", self.ship)
        taskMgr.remove(self.trail.motion_trail_task_name)
        self.trail.time_window = 0.4 # Length of trail
        self.trail.resolution_distance = 0.00001
        self.trail.register_motion_trail()
        #self.trail.set_depth_test(False)
        self.trail.geom_node_path.reparent_to(self.parent)
        self.trail.geom_node_path.node().set_attrib(
            ColorBlendAttrib.make(
                ColorBlendAttrib.M_add,
                ColorBlendAttrib.O_incoming_alpha,
                ColorBlendAttrib.O_one
            )
        )
        for v, pc in enumerate((
            (Point3(-0.11,  0.00, -0.05),Vec4(0,0,0,0)),
            (Point3(-0.08,  0.00, -0.05),Vec4(1,0,1,1)),
            (Point3(-0.05,  0.00, -0.05),Vec4(0,0,0,0)),
            (Point3(-0.00,  0.00, -0.05),Vec4(0,0,0,0)),
            (Point3( 0.05,  0.00, -0.05),Vec4(0,0,0,0)),
            (Point3( 0.08,  0.00, -0.05),Vec4(1,0,1,1)),
            (Point3( 0.11,  0.00, -0.05),Vec4(0,0,0,0)),
        )):
            pos, col = pc
            self.trail.add_vertex(pos)
            self.trail.set_vertex_color(v, col, col)
        self.accum_dt = 0
        self.trail.update_vertices()

    def update(self, tube_y, x=0, off=(0, 0, 0)):
        self.accum_dt += base.clock.dt
        transform = self.ship.get_transform(self.parent).get_mat()
        transform = transform * transform.translate_mat(x,tube_y,0)
        self.trail.geom_node_path.set_pos(Point3(-x, -tube_y, 0) + off)
        self.trail.transferVertices()
        self.trail.cmotion_trail.updateMotionTrail(self.accum_dt, transform)

    def reset(self):
        self.trail.reset_motion_trail()
        self.trail.reset_motion_trail_geometry()

    def destroy(self):
        self.reset()
        self.trail.delete()


class PathHistory:
    def __init__(self, max_length):
        self.max_length = max_length
        self.samples = []

    def append(self, t, v):
        while len(self.samples) > 0 and self.samples[-1][0] >= t:
            self.samples.pop()

        while len(self.samples) > 2 and self.samples[1][0] < t - self.max_length:
            self.samples.pop(0)

        self.samples.append((t, v))

    def sample(self, t):
        if t >= self.samples[-1][0]:
            t, v = self.samples[-1]
            return v

        if self.samples[0][0] >= t:
            t, v = self.samples[0]
            return v

        i = 0
        while len(self.samples) > 2 and self.samples[i + 1][0] < t:
            i += 1

        t0, v0 = self.samples[i]
        t1, v1 = self.samples[i + 1]
        if t0 == t1:
            return v0
        else:
            ti = (t - t0) / (t1 - t0)
            return v0 * (1 - ti) + v1 * ti

    def rewind(self, t):
        "Like sample, but also removes all samples after that point"

        if t >= self.samples[-1][0]:
            t, v = self.samples[-1]
            return v

        if self.samples[0][0] >= t:
            if len(self.samples) > 1:
                del self.samples[1:]
            t, v = self.samples[0]
            return v

        i = len(self.samples) - 2
        while i >= 0 and self.samples[i][0] > t:
            self.samples.pop()
            i -= 1

        t0, v0 = self.samples[i]
        t1, v1 = self.samples[i + 1]
        if t0 == t1:
            v = v0
        else:
            ti = (t - t0) / (t1 - t0)
            v = v0 * (1 - ti) + v1 * ti

        # Replace last sample with what we just interpolated
        self.samples[-1] = (t, v)
        return v


class Ship:
    def __init__(self):
        self.root = NodePath("dummy")
        self.ship = loader.load_model("assets/bam/ship/ship.bam")
        self.trail = ShipTrail(self.ship)
        #self.ship.set_hpr(90, 90, 90)
        self.ship.set_scale(0.05)
        self.ship.flatten_strong()
        self.ship.reparent_to(self.root)

        self.explosion = Actor("assets/bam/explosions/explosion_1.bam")
        self.explosion.reparent_to(self.ship)
        self.explosion.stash()
        self.explosion.set_p(90)
        self.explosion.set_bin('fixed', 40)
        self.explosion.show_through()
        self.explosion.set_attrib(
            ColorBlendAttrib.make(
                ColorBlendAttrib.M_add,
                ColorBlendAttrib.O_incoming_alpha,
                ColorBlendAttrib.O_one
            )
        )
        for mat in self.explosion.find_all_materials():
            mat.set_base_color((0, 0, 0, 1))
            mat.set_metallic(0)
            mat.set_emission((1, 1, 1, 1))
            self.explosion_mat = mat

    def explode(self, duration):
        self.explosion.unstash()
        self.explosion.set_scale(0.01)
        self.explosion.set_color_scale((1, 1, 1, 1))
        self.explosion.set_play_rate(2.0, "explode")
        self.explosion.play("explode")
        self.explosion.scaleInterval(0.2, 0.6, blendType='easeOut').start()
        self.explosion.colorScaleInterval(duration, (1, 1, 1, 0.3), blendType='easeInOut').start()

    def unexplode(self, duration):
        self.explosion.set_play_rate(-2.0, "explode")
        self.explosion.play("explode")
        Sequence(Wait(duration - 0.2), self.explosion.scaleInterval(0.2, 0.01, blendType='easeOut')).start()
        Sequence(self.explosion.colorScaleInterval(duration, (1, 1, 1, 1), blendType='easeInOut'), Func(self.explosion.stash)).start()


class ShipControls(DirectObject):
    def __init__(self, ship, tube):
        self.ship = ship
        self.tube = tube
        base.taskMgr.add(self.cam_move, sort=4)

        self.bounce_large = loader.load_sfx('assets/sfx/bump1.wav')
        self.bounce_small = loader.load_sfx('assets/sfx/enter.wav')
        self.rewind_sound = loader.load_sfx('assets/sfx/rewind.wav')

        self.steel_explode = loader.load_sfx('assets/sfx/explode.wav')
        self.flesh_explode = loader.load_sfx('assets/sfx/f_explode.wav')
        self.explode_reverse = loader.load_sfx('assets/sfx/explode_reverse.wav')

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

        self.history = PathHistory(max(CAM_TRAIL, REWIND_DIST))
        self.history.append(0, Vec4(0, base.camera.get_z(), 0, 0))

        self.static_tex = loader.load_texture("assets/static.webm")
        self.static_tex.set_minfilter(SamplerState.FT_nearest)
        self.static_tex.set_magfilter(SamplerState.FT_nearest)
        cm = CardMaker('card')
        cm.set_frame_fullscreen_quad()
        cm.set_uv_range(self.static_tex)
        self.static_plane = render2d.attach_new_node(cm.generate())
        self.static_plane.set_texture(self.static_tex)
        self.static_plane.set_attrib(
            ColorBlendAttrib.make(
                ColorBlendAttrib.M_add,
                ColorBlendAttrib.O_incoming_alpha,
                ColorBlendAttrib.O_one
            )
        )
        self.static_plane.set_alpha_scale(0.75)
        self.static_tex.loop = True
        self.static_plane.hide()

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

        self.r_speed = hor * SHIP_DONK_FACTOR

        self.update_ship_rotation(-hor, force=True)

    def crash(self):
        self.tube.pause()

        explode = self.steel_explode if self.tube.current_ring.level == 'steel' else self.flesh_explode
        explode.play()

        def rewind(y):
            self.tube.set_y(y)
            r, z, h, tilt = self.history.rewind(self.tube.y)
            #self.ship.root.set_r(r)
            #self.ship.ship.set_h(h)
            #self.ship.ship.set_r(tilt)

            current_ring = self.tube.current_ring
            radius = current_ring.radius_at(0.0) + current_ring.depth_at(0.0)
            z = SHIP_HEIGHT - radius
            self.ship.ship.set_z(z)

            self.z_target = z
            self.r_speed = 0

            # Update motion trail
            self.ship.trail.reset()
            for t, (r, z, h, tilt) in self.history.samples:
                if t < self.tube.y - 4.0:
                    continue
                self.ship.root.set_r(r)
                self.ship.ship.set_h(h)
                self.ship.ship.set_r(tilt)
                self.ship.trail.update(t)

        to_y = max(0, self.tube.y - REWIND_DIST)
        rewind_ival = LerpFunc(rewind, duration=REWIND_TIME, fromData=self.tube.y, toData=to_y, blendType='easeInOut')
        Sequence(
            Func(self.ship.explode, 1.0),
            Wait(1.5),
            Func(self.static_plane.show),
            Func(self.static_tex.play),
            Func(self.explode_reverse.play),
            Func(self.rewind_sound.play),
            Func(self.ship.unexplode, 0.3),
            Wait(0.3),
            rewind_ival,
            Func(self.static_plane.hide),
            Func(self.static_tex.stop),
            Func(self.tube.resume),
        ).start()

    def update_ship_rotation(self, hor, force=False):
        target_h = self.r_speed * 60 / ROT_SPEED_LIMIT
        target_r = hor * SHIP_ROLL_ANGLE
        if force:
            t = 0.0
        else:
            t = SHIP_ROLL_SPEED ** base.clock.dt
        self.ship.ship.set_hpr(target_h, 0, target_r * (1 - t) + self.ship.ship.get_r() * t)

    def update(self, dt):
        if self.tube.paused:
            #self.ship.trail.trail.geom_node_path.set_y(-self.tube.y)
            #self.ship.trail.update(self.tube.y)
            #self.ship.trail.update(self.tube.y)
            return

        is_down = base.mouseWatcherNode.is_button_down

        current_ring = self.tube.current_ring
        #self.set_ship_z_target(SHIP_HEIGHT - max(current_ring.start_radius + current_ring.start_depth, current_ring.end_radius + current_ring.end_depth))
        self.set_ship_z_target(SHIP_HEIGHT - current_ring.radius_at(0.0) - current_ring.depth_at(0.0))

        if USE_GRAVITY:
            z = self.ship.ship.get_z()
            if z > self.z_target:
                if current_ring.override_gravity is not None:
                    self.z_speed -= current_ring.override_gravity * dt
                else:
                    self.z_speed -= SHIP_Z_ACC * dt
                z += self.z_speed * dt

            if z < self.z_target:
                if abs(self.z_speed) < 0.1 or abs(self.z_target - z) < 0.1:
                    self.z_speed = -1
                    z = self.z_target
                elif self.z_speed < 0:
                    if self.z_speed < -BOUNCE_LARGE_THRESHOLD:
                        self.bounce_large.play()
                    else:
                        self.bounce_small.play()
                    z = self.z_target
                    self.z_speed = -self.z_speed * SHIP_BOUNCE
                else:
                    self.z_speed += SHIP_Z_ACC * dt

                z += self.z_speed * dt
                if z < self.z_target:
                    z = self.z_target
                    self.z_speed = -1

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
        h = self.ship.ship.get_h()
        tilt = self.ship.ship.get_r()
        if not self.tube.paused:
            self.history.append(self.tube.y, Vec4(r, z, h, tilt))

        # Calculate ship r and z some distance ago
        r, z, h, tilt = self.history.sample(self.tube.y - CAM_TRAIL)

        if z > self.ship.ship.get_z() + 0.5:
            z = self.ship.ship.get_z() + 0.5

        if z < self.ship.ship.get_z():
            z = self.ship.ship.get_z()

        #self.cam_root.set_pos(self.ship.root.get_pos())
        self.cam_root.set_r(r)
        base.camera.set_z(z + CAM_Z_OFFSET)
        #base.camera.look_at(self.ship.ship)

        return task.cont
