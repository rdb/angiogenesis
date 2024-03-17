from direct.showbase.ShowBase import ShowBase
from panda3d.core import Shader

from src.tube import Tube
from src.ship import Ship, ShipControls

base = ShowBase()
base.set_background_color((0, 0, 0, 1))


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


#base.taskMgr.add(move)

base.run()
