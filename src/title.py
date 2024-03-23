from random import uniform
from direct.interval.IntervalGlobal import *
from panda3d.core import LineSegs, Vec3, Fog
from .ship import ShipTrail



class Title:
    def __init__(self):
        base.camLens.set_near(4)
        base.camLens.set_far(3000)
        self.mega = loader.load_model("assets/bam/mega/mega.bam").copy_to(render)
        self.mega.set_pos(800,2500,0)
        self.mega.set_scale(50)
        Sequence(
            self.mega.quatInterval(100, (-180,0,0), startHpr=(0,0,0)),
            self.mega.quatInterval(100, (-360,0,0), startHpr=(-180,0,0)),
        ).loop()
        self.mega.scaleInterval(300, 150, blendType="easeOut").start()


        self.ship = loader.load_model("assets/bam/ship/ship.bam").copy_to(render)
        self.ship.set_pos(-1,25,-4)
        self.ship.look_at(self.mega)
        hpr = self.ship.get_hpr()
        pos = self.ship.get_pos()

        self.ship_rot_seq = Sequence(
            self.ship.quatInterval(10, hpr+( 4, 4,4), startHpr=hpr+(-4,-4,-4), blendType="easeInOut"),
            self.ship.quatInterval(10, hpr+(-4,-4,-4), startHpr=hpr+(4,4,4) ,blendType="easeInOut"),
        ).loop()
        self.ship_pos_seq = Sequence(
            self.ship.posInterval(15, pos+(-1,-1,-1), startPos=pos+( 1, 1,1), blendType="easeInOut"),
            self.ship.posInterval(15, pos+( 1, 1,1), startPos=pos+(-1,-1,-1), blendType="easeInOut"),
        ).loop()

        self.title = loader.load_model("assets/bam/title/title.bam").copy_to(render)
        self.title.set_pos(-4,5,0)
        self.title.set_p(90)
        self.title.set_h(40)

        self.title_seq = Sequence(
            self.title.quatInterval(10, (30,90,0), startHpr=(40,90,0), blendType="easeInOut"),
            self.title.quatInterval(10, (40,90,0), startHpr=(30,90,0), blendType="easeInOut"),
        ).loop()

        segs = LineSegs("starfield")
        def randvec(n):
            return Vec3(uniform(-n,n), uniform(-n,n), uniform(-n,n))

        for i in range(2048):
            v = randvec(1000)
            segs.set_color((1,1,1,1))
            segs.move_to(v)
            segs.draw_to(v+(0,2,0))
            segs.set_color((0,1,1,0))

        fields = render.attach_new_node("fields")
        field = fields.attach_new_node(segs.create())
        field_2 = field.copy_to(field)
        field_2.set_y(2000)
        field_3 = field.copy_to(field)
        field_3.set_y(4000)
        field.posInterval(10, pos=(0,-2000,0)).loop()
        fields.set_h(-20)

        fog = Fog("starfog")
        fog.set_color((0,0,0,1))
        fog.set_exp_density(0.002)
        fields.attach_new_node(fog)
        fields.set_fog(fog)

        self.a = 0
        self.trails = ShipTrail(self.ship)
        base.task_mgr.add(self.update)

        render.ls()

    def update(self, task):
        self.a += base.clock.dt
        self.trails.update(self.a)
        return task.cont
