from direct.showbase.ShowBase import ShowBase
from panda3d.core import load_prc_file, Filename, AmbientLight, SamplerState
import simplepbr

from src.tube import Tube
from src.ship import Ship, ShipControls
from src.donk import Collisions

from math import ceil


load_prc_file(Filename.expand_from("$MAIN_DIR/settings.prc"))

base = ShowBase()
base.set_background_color((0, 0, 0, 1))

env_pool = simplepbr.envpool.EnvPool.ptr()
env_map = env_pool.load('assets/env/aircraft_workshop_01.env')
env_map.cubemap.set_minfilter(SamplerState.FT_linear_mipmap_linear)
env_map.cubemap.set_magfilter(SamplerState.FT_linear_mipmap_linear)
env_map.filtered_env_map.set_minfilter(SamplerState.FT_linear_mipmap_linear)
env_map.filtered_env_map.set_magfilter(SamplerState.FT_linear_mipmap_linear)

simplepbr.init(
    max_lights=0,
    use_normal_maps=True,
    use_emission_maps=True,
    enable_shadows=False,
    enable_hardware_skinning=False,
    env_map=env_map,
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

donk = Collisions(tube, controls)


def update(task):
    # Run simulation at least every 20 ms
    dt = base.clock.dt
    num_steps = ceil(dt / 0.020)
    dt /= num_steps
    num_steps = min(10, num_steps)
    for i in range(num_steps):
        tube.update(dt)
        controls.update(dt)
        donk.update(dt)
    return task.cont

base.taskMgr.add(update, sort=1)

#base.render.set_render_mode_wireframe()

base.camLens.set_near(0.1)
base.camLens.set_fov(80)

base.disable_mouse()
#base.camera.reparent_to(ship.ship)
#base.camera.set_pos(0, -10, 0)

base.accept('f12', base.screenshot)


#base.taskMgr.add(move)

base.run()
