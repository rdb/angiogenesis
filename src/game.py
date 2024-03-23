from panda3d.core import (
    AudioSound,
)
from direct.interval.IntervalGlobal import Func, Sequence, Wait
from direct.gui.OnscreenText import OnscreenText

from .tube import Tube
from .ship import Ship, ShipControls
from .donk import Collisions
from .title import Title
from .space import Starfield
from .cutscene import Cutscene

from math import ceil


class Game:
    def __init__(self):
        self.title = Title()
        self.paused = False
        self.music = base.loader.load_music('assets/music/a/A-intro.mp3')
        self.music.set_loop(True)
        self.music.play()
        base.accept('space', self.launch)

        base.camLens.set_fov(80)

        self.starfield = Starfield()
        self.cutscene = Cutscene("assets/bam/cutscenes/cutscene.bam")

        loader.load_model('assets/bam/segments/segments.bam', callback=self.on_model_load)
        self.segments = None

        self.text = OnscreenText(text='Loading...', pos=(0, -0.7), fg=(1, 1, 1, 1))
        self.task = None

    def on_model_load(self, model):
        self.text.text = 'Press space to start'
        self.segments = model
        print("Model loaded.")

    def launch(self):
        base.ignore('space')
        self.title.destroy()
        self.title = None

        Sequence(self.text.colorScaleInterval(1.0, (0, 0, 0, 0)), Func(self.text.hide)).start()

        base.camLens.set_near_far(0.1, 60 * 40)
        self.cutscene.play('intro', self.launch_harder)

    def launch_harder(self):
        self.ship = Ship()
        self.ship.root.reparent_to(render)

        if not self.segments:
            # force loading now
            self.segments = loader.load_model('assets/bam/segments/segments.bam')

        self.tube = Tube(self.segments)
        self.tube.root.reparent_to(render)

        self.controls = ShipControls(self.ship, self.tube)

        self.donk = Collisions(self.tube, self.controls)

        base.cam.set_p(0)
        base.cam.reparent_to(base.camera)

        base.accept('endgame', self.game_end)
        base.accept('p', self.toggle_pause)
        self.task = base.taskMgr.add(self.update, sort=1)
        self.starfield.fields.hide()
        base.accept('e', self.game_end)

    def game_end(self):
        self.paused = True
        if self.task:
            self.task.remove()
        base.ignore('p')
        self.ship.destroy()
        self.controls.destroy()
        self.tube.destroy()
        self.donk.destroy()

        #self.cutscene.actor.set_p(-90)
        #self.cutscene.actor.set_y(2596.09)
        #self.cutscene.actor.set_z(40)
        #self.cutscene.actor.set_x(14)
        self.cutscene.play('einde1', self.game_endier)
        explode = loader.load_sfx('assets/sfx/f_explode.wav')
        #Sequence(Wait(2.0), Func(explode.play)).start()
        #print(base.cam.get_pos(render))
        #self.cutscene.actor.set_p(0)

    def game_endier(self):
        self.starfield.fields.show()
        base.camLens.set_near_far(0.1, 300)
        self.cutscene2 = Cutscene('assets/bam/cutscenes/cutscene2.bam')
        self.cutscene2.play('KeyAction', self.game_endiest, startFrame=25)

        explode = loader.load_sfx('assets/sfx/big_explosion.mp3')
        explode.play()

    def game_endiest(self):
        text = OnscreenText(text='thank you for playing', pos=(0, 0.0), fg=(1, 1, 1, 1))

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
        #if base.mouseWatcherNode.is_button_down('lshift'):
        #    dt *= 8
        num_steps = ceil(dt / 0.020)
        dt /= num_steps
        num_steps = min(10, num_steps)
        for i in range(num_steps):
            self.tube.update(dt)
            self.controls.update(dt)
            self.donk.update(dt)

        return task.cont
