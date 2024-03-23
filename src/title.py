from direct.interval.IntervalGlobal import *
from .ship import ShipTrail



class Title:
    def __init__(self):
        base.camLens.set_near(4)
        base.camLens.set_far(3000)
        self.root = render.attach_new_node('title')
        loader.load_model("assets/bam/mega/mega.bam", callback=self.on_load_mega)

        self.ship_parent = self.root.attach_new_node("ship_parent")
        self.ship_parent.set_pos(-1, 25, -4)
        self.ship = loader.load_model("assets/bam/ship/ship.bam").copy_to(self.ship_parent)
        self.ship.set_scale(0.05)
        self.ship.flatten_strong()
        self.ship.set_scale(20)
        pos = self.ship_parent.get_pos()
        hpr = self.ship.get_hpr()

        self.ship_rot_seq = Sequence(
            self.ship.quatInterval(10, hpr+( 4, 4,4), startHpr=hpr+(-4,-4,-4), blendType="easeInOut"),
            self.ship.quatInterval(10, hpr+(-4,-4,-4), startHpr=hpr+(4,4,4) ,blendType="easeInOut"),
        )
        self.ship_rot_seq.loop()
        self.ship_pos_seq = Sequence(
            self.ship_parent.posInterval(15, pos+(-1,-1,-1), startPos=pos+( 1, 1,1), blendType="easeInOut"),
            self.ship_parent.posInterval(15, pos+( 1, 1,1), startPos=pos+(-1,-1,-1), blendType="easeInOut"),
        )
        self.ship_pos_seq.loop()

        self.title = loader.load_model("assets/bam/title/title.bam").copy_to(self.root)
        self.title.set_pos(-4,5,0)
        self.title.set_p(90)
        self.title.set_h(40)
        self.title.set_bin('background', 10)

        self.title_seq = Sequence(
            self.title.quatInterval(10, (30,90,0), startHpr=(40,90,0), blendType="easeInOut"),
            self.title.quatInterval(10, (40,90,0), startHpr=(30,90,0), blendType="easeInOut"),
        )
        self.title_seq.loop()

        self.a = 0
        self.trails = ShipTrail(self.ship, parent=self.ship_parent)
        self.task = base.task_mgr.add(self.update)

    def on_load_mega(self, mega):
        mega.reparent_to(self.root)
        self.ship.look_at(mega)
        mega.set_pos(800,2500,0)
        mega.set_scale(50)
        Sequence(
            mega.quatInterval(100, (-180,0,0), startHpr=(0,0,0)),
            mega.quatInterval(100, (-360,0,0), startHpr=(-180,0,0)),
        ).loop()
        mega.scaleInterval(300, 150, blendType="easeOut").start()

    def destroy(self):
        self.ship_rot_seq.finish()
        self.ship_pos_seq.finish()
        self.title_seq.finish()
        self.task.remove()
        self.title.remove_node()
        self.ship_parent.remove_node()
        self.trails.destroy()
        self.root.remove_node()

    def update(self, task):
        self.a += base.clock.dt
        self.trails.update(self.a * 50, self.a * 15, (-0.25, -0.1, 0.6))
        return task.cont
