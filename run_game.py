from direct.showbase.ShowBase import ShowBase
from direct.actor.Actor import Actor
from panda3d.core import (
    load_prc_file,
    Filename,
    AmbientLight,
    SamplerState,
)
import simplepbr

from src.game import Game


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
    msaa_samples=4,
    max_lights=0,
    use_normal_maps=True,
    use_emission_maps=True,
    enable_shadows=False,
    enable_hardware_skinning=False,
    env_map=env_map,
)

for task in base.taskMgr.getTasksNamed('simplepbr update'):
    task.sort = 49

base.taskMgr.step()

alight = AmbientLight('alight')
alight.set_color((0, 0, 0, 1))
render.set_light(render.attach_new_node(alight))

base.disable_mouse()

game = Game()

base.accept('f12', base.screenshot)


#base.taskMgr.add(move)

base.run()
