import pyglet as pg
from constants import *
import utils

pg.resource.path = ['assets/']

VISI_NORMAL = 'visi_normal'
VISI_HIDDEN = 'visi_hidden'

SPRITE_GROUP_FOND = 'fond'
SPRITE_GROUP_FRUITS = 'fruit'
SPRITE_GROUP_EXPLOSIONS = 'explosions'
SPRITE_GROUP_MASQUE = 'masque'
SPRITE_GROUP_GUI = 'gui'

_groups = {
    SPRITE_GROUP_FOND : pg.graphics.Group( order = 0 ),
    SPRITE_GROUP_FRUITS : pg.graphics.Group( order = 1 ),
    SPRITE_GROUP_EXPLOSIONS : pg.graphics.Group( order = 2 ),
    SPRITE_GROUP_MASQUE : pg.graphics.Group( order = 3 ),
    SPRITE_GROUP_GUI : pg.graphics.Group( order = 4 )
}

def sprite_group(name): return _groups[name]
def batch():            return _g_batch
def groupe_gui():       return _groups[SPRITE_GROUP_GUI]
def groupe_masque():    return _groups[SPRITE_GROUP_MASQUE]

_g_batch = pg.graphics.Batch()   # optimization for display


class LineSprite( pg.shapes.Line ):
    """objet graphique de type ligne"""
    def __init__(self, a, b, color, thickness):
        super().__init__( x=a[0], y=a[1], x2=b[0], y2=b[1], thickness=thickness, 
            color=color, 
            batch=batch(), 
            group=sprite_group(SPRITE_GROUP_GUI) )
        self.anchor_position = (0, 0)

    def __del__(self):
        self.delete()   # removes the sprite from the graphics batch
        super().__del__()

    @classmethod
    def wall(cls, a, b):
        # Segments to build the jar
        return cls( a=a, b=b, thickness=WALL_THICKNESS, color=WALL_COLOR)

    @classmethod
    def redline(cls, a, b):
        # Maximum level red line
        return cls( a=a, b=b, thickness=REDLINE_THICKNESS, color=REDLINE_COLOR)


class SuikaSprite ( pg.sprite.Sprite ):

    def __init__(self, **kwargs):
        super().__init__(**kwargs)
        self._blink_start = None
        self._fadein_start = None 
        self._fadeout_start = None
        self._visibility = VISI_NORMAL

    @property
    def fadein(self):
        return bool(self._fadein_start)
    
    @fadein.setter
    def fadein(self, activate ):
        if( activate and not self._fadein_start ):
            self._fadein_start = utils.now()
            self._fadeout_start = None
        elif( not activate ):
            self._fadein_start = None


    @property
    def fadeout(self):
        return bool(self._fadeout_start)
    
    @fadeout.setter
    def fadeout(self, activate):
        if( activate and not self._fadeout_start ):
            self._fadein_start = None
            self._fadeout_start = utils.now()
        elif( not activate ):
            self._fadeout_start = None


    @property
    def blink(self):
        return bool(self._blink_start)
    
    @blink.setter
    def blink(self, activate):
        if( activate and not self._blink_start ):
            self._blink_start = utils.now()
        elif( not activate ):
            self._blink_start = None


    @property
    def visibility(self):
        return self._visibility
    
    @visibility.setter
    def visibility(self, visi):
        if (visi == VISI_NORMAL):
            self._opacity_ref = 255
            self.visible = True
        elif(visi == VISI_HIDDEN ):
            self.visible = False
        else:
            print(f"warning: unknown visibility value {visi}")


    # intercepts the pyglet.spite.Sprite update to process animations
    def update(self, x, y, rotation, on_animation_stop):
        # position processed by pyglet
        pg.sprite.Sprite.update( self, x=x, y=y, rotation=rotation )

        # animation management
        coef_size = 1.0
        coef_opacity = 1.0

        # fadein
        if( self._fadein_start ):
            assert( not self.fadeout )
            t = utils.now() - self._fadein_start
            a =  t * (1-FADE_SIZE)/FADEIN_DELAY + FADE_SIZE
            if( a >= FADEIN_OVERSHOOT ):
                self.fadein = False
                if( on_animation_stop ):
                    on_animation_stop()
            coef_size = min( FADEIN_OVERSHOOT, a )
            coef_opacity = min (1, a)

        # fadeout
        if( self._fadeout_start ):
            assert( not self.fadein )
            t = utils.now() - self._fadeout_start
            a =  (FADEOUT_DELAY - t) / FADEOUT_DELAY
            if( a < 0 ):
                #self.fadeout = False   # do not remove the effect otherwise the sprite reappears
                if( on_animation_stop ):
                    on_animation_stop()
            coef_size = max(0.2, a)
            coef_opacity = max( 0, a )

        # blink changes opacity multiplicatively with other animations
        if( self._blink_start ):
            dt = utils.now() - self._blink_start
            if( dt > 0 ):
                coef_opacity *= (0.5 + abs(( (BLINK_FREQ * dt) % 1) - 0.5))

        self.scale_x = self._scale_ref[0] * coef_size
        self.scale_y = self._scale_ref[1] * coef_size
        if( hasattr( self, '_opacity_ref') ):
            self.opacity = int(self._opacity_ref  * coef_opacity)


class FruitSprite( SuikaSprite ):
    def __init__(self, nom, r, group=None):
        #  pyglet sprite associated with the physics object
        if( group is None ):
            group = sprite_group(SPRITE_GROUP_FRUITS)
        img = pg.resource.image( f"{nom}.png" )
        img.anchor_x = img.width // 2                 # anchor to the center of the image
        img.anchor_y = img.height // 2
        self._scale_ref = (2 * r / img.width,  2 * r / img.height)

        super().__init__(img=img, 
                         batch=batch(), 
                         group=sprite_group(SPRITE_GROUP_FRUITS) )


class PreviewSprite( FruitSprite ):
    """ fruits en attente (non associé à un objet pymunk)
    """
    def __init__(self, nom, width=PREVIEW_SPRITE_SIZE, refcnt=None ):
        super().__init__(nom, r=width/2, group=sprite_group(SPRITE_GROUP_GUI) )

    def update(self, x, y):
         super().update( x=x, y=y, rotation=0, on_animation_stop=None )


## Explosion
EXPLO_SIZE = 256
EXPLO_PNG = "explosion.png"
EXPLO_CENTRES = [ 
    # line 1
    (206,625),
    (437,625),
    (665,625),
    (904,625),
    (1151,625),
    (1435,625),
    (1712,625),
    #line 2 
    (205,275),
    (456,275),
    (708,275),
    (949,275),
    (1204,275),
    (1456,275),
    (1712,275),
]


def _make_sequence():
    img = pg.resource.image(EXPLO_PNG)
    seq = []
    for (x,y) in EXPLO_CENTRES:
        region = img.get_region( x=x-EXPLO_SIZE//2, y=y-EXPLO_SIZE//2, 
                                    width=EXPLO_SIZE, height=EXPLO_SIZE )
        region.anchor_x = EXPLO_SIZE//2
        region.anchor_y = EXPLO_SIZE//2
        seq.append(region)
    return pg.image.Animation.from_image_sequence( 
        sequence=seq, 
        loop=False,
        duration=EXPLOSION_DELAY / len(seq))


# global variable to avoid recreating the sequence with each explosion.
_sequence_explosion = _make_sequence()

class ExplosionSprite( SuikaSprite ):
    def __init__(self, r, on_explosion_end):
        # setup callback
        self._on_explosion_end = on_explosion_end
        # build actual sprite
        super().__init__(img=_sequence_explosion,
                         batch = batch(),
                         group=sprite_group(SPRITE_GROUP_EXPLOSIONS))

        scale = 2.5 * r / EXPLO_SIZE
        self._scale_ref = ( scale, scale )
        self.opacity=128

    # Event sent by pyglet automatically
    def on_animation_end(self):
        # returns the event to the parent Fruit object
        self._on_explosion_end()