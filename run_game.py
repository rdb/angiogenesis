from direct.showbase.ShowBase import ShowBase
from panda3d.core import (
    load_prc_file,
    Filename,
    AmbientLight,
    SamplerState,
    AudioSound,
)
import simplepbr

from src.tube import Tube
from src.ship import Ship, ShipControls
from src.donk import Collisions
from src.title import Title

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

alight = AmbientLight('alight')
alight.set_color((0, 0, 0, 1))
render.set_light(render.attach_new_node(alight))


class Game:
    def __init__(self):
        self.title = Title()
        self.paused = False
        self.music = base.loader.load_music('assets/music/a/A-intro.mp3')
        self.music.set_loop(True)
        self.music.play()
        base.accept('space', self.launch)

    def launch(self):
        base.ignore('space')
        self.title.destroy()
        self.title = None

        base.camLens.set_near_far(0.1, 60 * 40)

        self.ship = Ship()
        self.ship.root.reparent_to(render)

        self.tube = Tube()
        self.tube.root.reparent_to(render)

        self.controls = ShipControls(self.ship, self.tube)

        self.donk = Collisions(self.tube, self.controls)

        base.accept('p', self.toggle_pause)
        base.taskMgr.add(self.update, sort=1)

    def toggle_pause(self):
        self.paused = not self.paused

    def update(self, task):
        if self.paused:
            return task.cont

        dt = base.clock.dt

        if self.music.status() == AudioSound.PLAYING:
            new_volume = max(0, self.music.get_volume() - dt)
            self.music.set_volume(new_volume)
            if new_volume == 0.0:
                self.music.stop()

        # Run simulation at least every 20 ms
        if base.mouseWatcherNode.is_button_down('lshift'):
            dt *= 8
        num_steps = ceil(dt / 0.020)
        dt /= num_steps
        num_steps = min(10, num_steps)
        for i in range(num_steps):
            self.tube.update(dt)
            self.controls.update(dt)
            self.donk.update(dt)

        return task.cont


#base.render.set_render_mode_wireframe()

#base.camLens.set_near(0.1)
base.camLens.set_fov(80)

base.disable_mouse()

game = Game()

base.accept('f12', base.screenshot)


#base.taskMgr.add(move)

base.run()
