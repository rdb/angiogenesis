from panda3d.core import *
from math import floor, ceil


DONK_DEBUG = False


class Collisions:
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

        self.trav = CollisionTraverser()
        self.trav.add_collider(self.cship, self.pusher)

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

        taskMgr.add(self.update, 'update collisions', sort=3)

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

    def update(self, task):
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

            cnode0 = ring.collision_nodes[i0]
            cnode1 = ring.collision_nodes[i1] if i0 != i1 else None

            ship_x = ship_r * ring.r_to_x

            x0 = (((i0 / seg_count) - ship_r) % 1.0) * ring.r_to_x
            x1 = (((i1 / seg_count) - ship_r) % 1.0) * ring.r_to_x

            if x0 > ring.r_to_x // 2:
                x0 -= ring.r_to_x
            if x1 > ring.r_to_x // 2:
                x1 -= ring.r_to_x

            if cnode0 is not None:
                cnode_path = cnode0.copy_to(self.croot)
                cnode_path.set_pos(x0, ring.node_path.get_y(), 0)
                if DONK_DEBUG:
                    cnode_path.show()

            if cnode1 is not None:
                cnode_path = cnode1.copy_to(self.croot)
                cnode_path.set_pos(x1, ring.node_path.get_y(), 0)
                if DONK_DEBUG:
                    cnode_path.show()

        self.trav.traverse(self.croot)

        moved = self.cship.get_pos()
        if moved.x != 0 or moved.y != 0:
            deflect = moved.x / current_ring.r_to_x
            pain = -moved.xy.normalized().y
            self.controls.donk(deflect, pain)

        self.cship.set_pos(0, 0, 0.2)

        return task.cont
