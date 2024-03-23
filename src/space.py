from panda3d.core import LineSegs, Vec3, Fog

from random import uniform


class Starfield:
    def __init__(self):
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
        self.fields = fields

    def destroy(self):
        self.fields.remove_node()
