from direct.showbase.DirectObject import DirectObject
from panda3d.core import *
from math import floor, ceil
from random import random, choice


DONK_DEBUG = False
SCRAPE_FADEOUT_SPEED = 2.0


class Collisions(DirectObject):
    def __init__(self, tube, controls):
        self.tube = tube
        self.controls = controls

        # This scene graph is just for collisions, doesn't relate to anything
        # in render
        self.croot = NodePath("collisions")
        #self.croot.reparent_to(render)

        self.cship = self.croot.attach_new_node(CollisionNode("ship"))
        self.cship.node().add_solid(CollisionSphere((0, 0, 0), 0.1))

        self.pusher = CollisionHandlerPusher()
        self.pusher.add_collider(self.cship, self.cship)
        self.pusher.add_in_pattern('into-%(material)it')

        base.accept('into-flesh', self.bump_flesh)
        base.accept('into-steel', self.bump_steel)

        self.trav = CollisionTraverser()
        self.trav.add_collider(self.cship, self.pusher)

        self.scraping = 0.0
        self.scrape = None

        self.steel_bumps = [
            base.loader.load_sfx('assets/sfx/bump1.wav'),
            base.loader.load_sfx('assets/sfx/bump2.wav'),
        ]

        self.steel_scrape = base.loader.load_sfx('assets/sfx/scratch.wav')
        self.steel_scrape.set_loop(True)

        self.flesh_bumps = [
            base.loader.load_sfx('assets/sfx/f_bump1.wav'),
            base.loader.load_sfx('assets/sfx/f_bump2.wav'),
            base.loader.load_sfx('assets/sfx/f_bump3.wav'),
        ]

        self.flesh_scrape = base.loader.load_sfx('assets/sfx/f_scratch.wav')
        self.flesh_scrape.set_loop(True)

        if DONK_DEBUG:
            self.cship.show()
            self.trav.show_collisions(self.croot)

            lens = PerspectiveLens()
            lens.set_near_far(0.01, 80)
            lens.set_fov(30)
            cam = self.make_debug_camera((0.4, 0.6, 0.7, 0.9), lens=lens)
            cam.set_y(-5)

            lens = OrthographicLens()
            lens.set_film_size(5, 100)
            lens.set_near_far(-5, 5)
            cam = self.make_debug_camera((0.8, 0.95, 0.05, 0.95), lens=lens)
            cam.look_at(0, 0, -1)

    def make_debug_camera(self, frame, lens):
        frame = Vec4(frame)

        cm = CardMaker('card')
        cm.set_frame(frame * 2 - 1)
        card = render2d.attach_new_node(cm.generate())
        card.set_transparency(1)
        card.set_color(0, 0, 0, 0.75)

        camera = base.make_camera(base.win, sort=100, scene=self.croot, displayRegion=frame, lens=lens)
        camera.reparent_to(self.cship)
        return camera

    def update(self, dt):
        if self.tube.paused:
            return

        self.croot.node().remove_all_children()
        self.cship.reparent_to(self.croot)

        ship_z = self.controls.get_ship_z_above_ground()
        self.cship.set_pos(0, 0, ship_z)

        ship_r = self.controls.ship.root.get_r() / -360.0

        current_ring = self.tube.current_ring
        for ring in (current_ring, self.tube.next_ring):
            seg_count = len(ring.collision_nodes)

            i0 = int(floor(ship_r * seg_count)) % seg_count
            i1 = int(ceil(ship_r * seg_count)) % seg_count

            cnodes0 = ring.collision_nodes[i0]
            cnodes1 = ring.collision_nodes[i1] if i0 != i1 else ()

            ship_x = ship_r * ring.r_to_x

            x0 = (((i0 / seg_count) - ship_r) % 1.0) * ring.r_to_x
            x1 = (((i1 / seg_count) - ship_r) % 1.0) * ring.r_to_x

            if x0 > ring.r_to_x // 2:
                x0 -= ring.r_to_x
            if x1 > ring.r_to_x // 2:
                x1 -= ring.r_to_x

            if cnodes0 is not None:
                for cnode_path in cnodes0:
                    cnode_path = cnode_path.copy_to(self.croot)
                    cnode_path.set_pos(x0, ring.node_path.get_y(), 0)
                    if DONK_DEBUG:
                        cnode_path.show()

            if cnodes1 is not None:
                for cnode_path in cnodes1:
                    cnode_path = cnode_path.copy_to(self.croot)
                    cnode_path.set_pos(x1, ring.node_path.get_y(), 0)
                    if DONK_DEBUG:
                        cnode_path.show()

        self.trav.traverse(self.croot)

        moved = self.cship.get_pos()
        if moved.x != 0 or moved.y != 0:
            deflect = moved.x / current_ring.r_to_x
            pain = -moved.xy.normalized().y

            if pain > 0.8 and not base.mouseWatcherNode.is_button_down('lshift'):
                if self.scrape:
                    self.scrape.stop()
                self.scraping = 0.0
                self.controls.crash()
            else:
                self.controls.donk(deflect, pain)
                if not self.scraping:
                    new_scrape = self.steel_scrape if current_ring.level == 'steel' else self.flesh_scrape
                    if self.scrape != new_scrape:
                        if self.scrape:
                            self.scrape.stop()
                        self.scrape = new_scrape

                    self.scrape.set_volume(1.0)
                    if self.scrape.status() != AudioSound.PLAYING:
                        self.scrape.set_time(0.2)
                        self.scrape.play()

                self.scraping += dt

        elif self.scraping:
            if self.scraping < 0.1 and self.scrape:
                self.scrape.stop()
            self.scraping = 0

        if not self.scraping and self.scrape:
            volume = self.scrape.get_volume()
            self.scrape.set_volume(max(volume - dt * SCRAPE_FADEOUT_SPEED, 0))
            if volume == 0.0:
                self.scrape.stop()
                self.scrape = None

        self.cship.set_pos(0, 0, ship_z)

    def bump_flesh(self, entry):
        sound = choice(self.flesh_bumps)
        sound.set_play_rate(0.5 + random())
        sound.play()

    def bump_steel(self, entry):
        sound = choice(self.steel_bumps)
        sound.set_play_rate(0.5 + random())
        sound.play()
