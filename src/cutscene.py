from direct.interval.IntervalGlobal import Sequence, Func
from direct.actor.Actor import Actor

from panda3d.core import (
    OmniBoundingVolume,
)


class Cutscene:
    def __init__(self, path):
        self.actor = Actor(path)
        self.actor.node().set_bounds(OmniBoundingVolume())
        self.actor.node().set_final(True)
        self.actor.hide()
        self.camera_joint = None
        for joint in self.actor.get_joints():
            if joint.name == 'camera':
                self.camera_joint = joint

    def play(self, name, callback, **kwargs):
        self.actor.show()
        self.actor.reparent_to(render)

        if self.camera_joint:
            joint = self.actor.expose_joint(None, 'modelRoot', 'camera')
            base.cam.reparent_to(joint)
            base.cam.set_hpr(0, -90, 0)
        else:
            base.cam.reparent_to(render)
            base.cam.set_pos(0, -130, 0)
            base.cam.set_hpr(0, 0, 0)
        Sequence(self.actor.actorInterval(name, **kwargs), Func(self.cleanup), Func(callback)).start()

    def cleanup(self):
        print("cleanup")
        base.cam.set_p(0)
        base.cam.reparent_to(base.camera)
        self.actor.detach_node()
