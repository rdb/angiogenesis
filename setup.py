from setuptools import setup

setup(
    name="angiogenesis",
    options = {
        'build_apps': {
            'include_patterns': [
                'settings.prc',
                'assets/**/*.bam',
                'assets/env/*.env',
                'assets/**/*.jpg',
                'assets/**/*.png',
                'assets/**/*.ogg',
                'assets/sfx/*.wav',
                'assets/sfx/*.mp3',
                'assets/glsl/*.*',
                'assets/metal lord.otf',
                'assets/static.mp4',
            ],
            'gui_apps': {
                'angiogenesis': 'run_game.py',
            },
            'log_filename': '$USER_APPDATA/Angiogenesis/output.log',
            'log_append': False,
            'plugins': [
                'pandagl',
                'p3ffmpeg',
                'p3openal_audio',
            ],
        }
    }
)
