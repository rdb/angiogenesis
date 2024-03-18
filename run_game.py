from direct.showbase.ShowBase import ShowBase
from panda3d.core import load_prc_file, Filename, AmbientLight
import simplepbr

from src.tube import Tube
from src.ship import Ship, ShipControls


load_prc_file(Filename.expand_from("$MAIN_DIR/settings.prc"))

base = ShowBase()
base.set_background_color((0, 0, 0, 1))

simplepbr.init(
    max_lights=0,
    use_normal_maps=True,
    use_emission_maps=True,
    enable_shadows=False,
    enable_hardware_skinning=False,
    env_map='assets/env/aircraft_workshop_01.env',
)

for task in base.taskMgr.getTasksNamed('simplepbr update'):
    task.sort = 49

alight = AmbientLight('alight')
alight.set_color((0, 0, 0, 1))
render.set_light(render.attach_new_node(alight))

tube = Tube()
tube.root.reparent_to(render)

ship = Ship()
ship.root.reparent_to(render)

controls = ShipControls(ship, tube)

#base.render.set_render_mode_wireframe()

base.camLens.set_near(0.1)
base.camLens.set_fov(80)

base.disable_mouse()
#base.camera.reparent_to(ship.ship)
#base.camera.set_pos(0, -10, 0)

base.accept('f12', base.screenshot)


#base.taskMgr.add(move)

base.run()
