import random

import pyglet as pg
import pymunk as pm

from constants import *
import utils

from sprites import VISI_NORMAL, VISI_HIDDEN
from sprites import FruitSprite, ExplosionSprite


_FRUITS_DEF_ORIGINAL = [
    # The rank in this list serves as kind/points/collision_type;  
    # Value 0 is reserved for types without handlers.  
    None,       
    {'mass':5,  'radius':30,  'name':'cherry' },
    {'mass':7,  'radius':40,  'name':'strawberry' },
    {'mass':10, 'radius':55,  'name':'plum' },
    {'mass':12, 'radius':70,  'name':'apricot' },
    {'mass':15, 'radius':90,  'name':'orange' },
    {'mass':20, 'radius':120, 'name':'tomato' },
    {'mass':25, 'radius':130, 'name':'grapefruit' },
    {'mass':30, 'radius':150, 'name':'apple' },
    {'mass':37, 'radius':190, 'name':'pineapple' },
    {'mass':40, 'radius':230, 'name':'melon' },
    {'mass':50, 'radius':200, 'name':'watermelon' },
]


def mode_mini(fruits):
    ret = [None]
    for f in fruits[1:]:
        fruit_mini = {}
        for k,v in f.items():
            if( k=='radius' ):
                fruit_mini[k] = v/4
            else:
                fruit_mini[k] = v
        ret.append( fruit_mini)
    return ret


_FRUITS_DEF = _FRUITS_DEF_ORIGINAL
#_FRUITS_DEF = mode_mini( _FRUITS_DEF_ORIGINAL )
_FRUITS_RANDOM = [ 1,2,3,4 ]

def nb_fruits():
    return len(_FRUITS_DEF) - 1

MODE_WAIT = 'wait'
MODE_FIRST_DROP = 'first_drop'
MODE_NORMAL = 'normal'
MODE_DRAG = 'drag'
MODE_MERGE = 'merge'
MODE_REMOVED = 'removed'

SPRITE_MAIN = "sprite_main"
SPRITE_EXPLOSION = "sprite_explosion"

COLLISION_CAT = 'coll_cat'
COLLISION_MASK = 'coll_mask'
BODY_TYPE = 'body_type'
VISI = 'visi'


_FRUIT_MODES = {
    MODE_WAIT: {
        COLLISION_CAT: CAT_FRUIT_WAIT,
        COLLISION_MASK: 0x00, # Collision with walls only  
        VISI: VISI_NORMAL,
        BODY_TYPE: pm.Body.KINEMATIC
    },
    MODE_FIRST_DROP: {
        COLLISION_CAT: CAT_FRUIT_DROP,
        COLLISION_MASK: CAT_FRUIT, # Collision with fruits and walls, but not with MAXLINE or other fruits FIRST_DROP  
        VISI: VISI_NORMAL,
        BODY_TYPE: pm.Body.KINEMATIC
    },
    MODE_NORMAL: {
        COLLISION_CAT: CAT_FRUIT,
        COLLISION_MASK: CAT_FRUIT_DROP | CAT_FRUIT | CAT_MAXLINE,
        VISI: VISI_NORMAL,
        BODY_TYPE: pm.Body.DYNAMIC
    },
    MODE_DRAG: {
        COLLISION_CAT: CAT_FRUIT,
        COLLISION_MASK: CAT_FRUIT_DROP | CAT_FRUIT | CAT_MAXLINE,
        VISI: VISI_NORMAL,
        BODY_TYPE: pm.Body.KINEMATIC
    },
    MODE_MERGE: {
        COLLISION_CAT: CAT_FRUIT_MERGE,
        COLLISION_MASK: 0x00,   # Collision with walls only  

        VISI: VISI_NORMAL,
        BODY_TYPE: pm.Body.KINEMATIC
    },
    MODE_REMOVED: {
        COLLISION_CAT: CAT_FRUIT_REMOVED,
        COLLISION_MASK: 0x00,   # Collision with walls only  
        VISI: VISI_HIDDEN,
        BODY_TYPE: pm.Body.KINEMATIC
    }
}


_g_fruit_id = 0
def _get_new_id():
    global _g_fruit_id
    _g_fruit_id +=1
    return _g_fruit_id


# FOR DEBUG: Mode changes allowed 
g_valid_transitions = {
    MODE_WAIT : (MODE_FIRST_DROP, MODE_NORMAL, MODE_REMOVED),    # Initial mode at creation  
    MODE_FIRST_DROP : (MODE_NORMAL, MODE_MERGE, MODE_REMOVED),
    MODE_NORMAL : (MODE_MERGE, MODE_DRAG, MODE_REMOVED),
    MODE_DRAG : (MODE_NORMAL, MODE_MERGE, MODE_REMOVED),
    MODE_MERGE : (MODE_REMOVED,),
    MODE_REMOVED : (MODE_REMOVED,)
}


def random_kind():
    return random.choice( _FRUITS_RANDOM )

def name_from_kind(kind):
    return _FRUITS_DEF[kind]["name"]


class AnimatedCircle( pm.Circle ):
    def __init__(self, **kwargs ):
        super().__init__(**kwargs)
        self._grow_start = None
        self._radius_ref = self.radius
    
    def grow_start( self ):
        """Starts an animation that varies the radius over time."""
        if( self._grow_start is None ):
            self._grow_start = utils.now()

    def update_animation(self):
        """Modifies the radius of the circle."""
        if( not self._grow_start ):
            return
        t = utils.now()-self._grow_start
        x = t * (1-FADE_SIZE)/ FADEIN_DELAY + FADE_SIZE
        self.unsafe_set_radius( self._radius_ref * min(1, x) )
        if( x > 1 ):
            self._grow_start = None


class Fruit( object ):
    def __init__(self, space, position, on_remove=None, kind=0, mode=MODE_WAIT):
        # Random species if not specified  
        assert kind<=nb_fruits(), "Unknown fruit type"  
        assert position
        if( kind<=0 ):
            kind = random_kind()
        fruit_def = _FRUITS_DEF[kind]

        self._id = _get_new_id()
        self._kind = kind
        self._space = space
        self._on_remove = on_remove
        self._body, self._shape = self._make_shape(
            radius=fruit_def['radius'],
            mass=fruit_def['mass'], 
            position=position)
        self._shape.collision_type = kind
        space.add(self._body, self._shape)

        self._sprites = { 
            SPRITE_MAIN : FruitSprite( 
                nom=fruit_def['name'], 
                r=fruit_def['radius'] )
        }
        self._fruit_mode = None
        self._dash_start_time = None
        self._drag_offset = None
        self._set_mode( mode )
        #print( f"{self} created" )


    def __del__(self):
        assert(    self._body is None 
               and self._shape is None 
               and len(self._sprites)==0
               and self._fruit_mode == MODE_REMOVED), "Resources not released"


    def __repr__(self):
        return f"{_FRUITS_DEF[self._kind]['name']}#{self._id}"


    def _make_shape(self, radius, mass, position):
        """Creates the pymunk body/shape for the physics simulation."""
        body = pm.Body(body_type = pm.Body.KINEMATIC)
        body.position = position
        shape = AnimatedCircle(body=body, radius=radius)
        shape.mass = mass
        shape.friction = FRICTION
        shape.elasticity = ELASTICITY_FRUIT
        # Adds fruit_id as a custom attribute of the pymunk object  
        shape.fruit = self
        return body, shape


    def release_ressources(self):
        if( not self.removed ):
            print( f"WARNING: {self} delete() called with mode different from MODE_REMOVED ({self._fruit_mode})" )
        # remove pymunk objects and local references
        if( self._body or self._shape):
            self._space.remove( self._body, self._shape )
            self._body = self._shape = None
        for k,sprite in self._sprites.items():
            sprite.delete()
        self._sprites = {}

    # Only used to move the pending fruit (next_fruit)  
    def on_window_resize(self, width, height):
        if(self._fruit_mode != MODE_WAIT):
            print(f"{self} WARNING: on_resize() ignored in mode {self._fruit_mode}")
            return
        fruit_def = _FRUITS_DEF[self._kind]
        x = width//2
        y = height - fruit_def['radius'] - 5
        self.position = pm.Vec2d(x,y)


    @property
    def id(self):
        return self._id

    @property
    def kind(self):
        return self._kind

    @property
    def scalar_velocity(self):
        return self._body.velocity.length

    @property
    def points(self):
        return self._kind

    @property
    def removed(self):
        return self._fruit_mode == MODE_REMOVED
    
    @property
    def position(self):
        return self._body.position

    @position.setter
    def position(self, pos):
        assert self._body.body_type != pm.Body.DYNAMIC
        self._body.position = pos

    @property
    def radius(self):
        return self._shape.radius

    def _is_deleted(self):
        return (self._body==None 
            and self._shape==None
            and self._sprites==None )


    def _set_mode(self, mode):
        # debug
        # old = self._fruit_mode
        # log = f"{self} mode {self._fruit_mode}->{mode}"
        # if( old and mode not in g_valid_transitions[old] ):
        #     log += " INVALIDE"
        # print(log)
        if(self.removed):
            return

        self._fruit_mode = mode
        attrs = _FRUIT_MODES[self._fruit_mode]

        # DYNAMIC or KINEMATIC  
        self._body.body_type = attrs[BODY_TYPE]

        # Sprites visibility  
        for s in self._sprites.values( ):
            s.visibility = attrs[VISI]

        # Modifies the collision rules  
        self._shape.filter = pm.ShapeFilter(
            categories= attrs[COLLISION_CAT],
            mask = attrs[COLLISION_MASK] | CAT_WALLS )  # collision systematique avec les murs


    def update(self):
        """Updates the fruit's sprite based on the physics simulation and other factors."""
        if( self.removed or self._is_deleted() ):
            return
        (x, y) = self._body.position
        degres = -180/3.1416 * self._body.angle  # pymunk and pyglet have opposite rotation directions  
        for s in self._sprites.values():
            s.update( x=x, y=y, rotation=degres, on_animation_stop=None )
        self._shape.update_animation()



    def blink(self, activate, delay=0):
        if(not activate):
            self._sprites[SPRITE_MAIN].blink = False
        elif( not self._sprites[SPRITE_MAIN].blink ):
            self._sprites[SPRITE_MAIN].blink = True


    def drop(self):
        """Sets the object to dynamic mode so it falls and enables collisions."""  
        self._body.velocity = (0, -INITIAL_VELOCITY)
        self._set_mode( MODE_FIRST_DROP )
        self._shape.collision_type = COLLISION_TYPE_FIRST_DROP


    def normal(self):
        """Sets the object to dynamic mode so it falls and enables collisions."""  
        self._set_mode( MODE_NORMAL )
        self._shape.collision_type = self._kind


    def fade_in(self):
        """Makes the sprite appear with a scaling and transparency effect."""  
        if(self.removed):
            return
        #print( f"{self}.fade_in()")
        self.normal()
        self._sprites[SPRITE_MAIN].fadein = True
        self._shape.grow_start()


    def fade_out(self):
        assert( self._body.body_type == pm.Body.KINEMATIC )
        self.normal()
        self._sprite[SPRITE_MAIN].fadeout = True


    def drag_mode(self, cursor):
        if( cursor ):
            self._drag_offset = - self._body.position + cursor
            self._set_mode( MODE_DRAG )
        else:
            self._drag_offset = None
            self._set_mode( MODE_NORMAL )


    def drag_to(self, cursor, dt):
        if( self._fruit_mode not in [MODE_NORMAL, MODE_DRAG] ):
            return
        assert self._drag_offset,   "Incorrect initialization of drag mode"  
        assert self._fruit_mode == MODE_DRAG,     "Drag mode not initialized"  
        self.set_velocity_to( dest= cursor-self._drag_offset, delay=dt*10 )


    def merge_to(self, dest):
        if( self._fruit_mode==MODE_MERGE):
            return
        self._set_mode( MODE_MERGE )  # No more collisions with fruits  
        self.set_velocity_to(dest, delay=MERGE_DELAY)
        pg.clock.schedule_once(lambda dt : self.remove(), delay=MERGE_DELAY )


    def set_velocity_to(self, dest, delay):
        (x0, y0) = self._body.position
        (x1, y1) = dest
        v = pm.Vec2d((x1-x0)/delay, (y1-y0)/delay)
        if( v.length < 0.00001 ):
            v= (0,0)
        self._body.velocity = v


    def explose(self):
        if( self._fruit_mode in [MODE_MERGE, MODE_REMOVED] ):
            return
        self._set_mode(MODE_MERGE)
        explo = ExplosionSprite( 
            r=self._shape.radius, 
            on_explosion_end=self.remove)
        explo.position = ( *self._body.position, 1)
        self._sprites[SPRITE_EXPLOSION] = explo
        self._sprites[SPRITE_MAIN].fadeout = True


    def is_offscreen(self) -> bool :
        if self._is_deleted():
            return False
        x, y = self._body.position
        return y < -WINDOW_HEIGHT 
    
    # Removes the fruit from the game. The object should no longer be used afterward.  
    def remove(self):
        # Optional callback (e.g., score management)  
        if(self._on_remove ):
            self._on_remove( self )
        self._set_mode(MODE_REMOVED)
        self.release_ressources()


class ActiveFruits(object):

    def __init__(self, space, width, height):
        self._space = space
        self._fruits = dict()
        self._score = 0
        self._next_fruit = None
        self._window_size = ( width, height )
        self._is_gameover = False

    def __len__(self):
        return len(self._fruits)

    def reset(self):
        self._is_gameover = False
        self.remove_all()
        self.remove_next()
        self._score = 0
        pg.clock.unschedule( self.explose_seq )

    def update(self):
        if( self._next_fruit ):
            self._next_fruit.update()
        for f in self._fruits.values():
            f.update()

    def prepare_next(self, kind):
        """Creates a fruit waiting to be dropped."""
        assert( not self._is_gameover )
        if( self._next_fruit ):
            print(("next_fruit already present"))
            return
        self._next_fruit = Fruit(space=self._space,
                                 kind=kind, 
                                 position=self._next_position(),
                                 on_remove=self.on_remove)
        # self.add() appelé dans play_next()

    def drop_next(self, position):
        if( (not self._next_fruit) or self._is_gameover ):
            return
        self._next_fruit.position = position
        self._next_fruit.drop()
        self.add( self._next_fruit )
        self._next_fruit = None

    def peek_next(self):
        return self._next_fruit

    def remove(self, id):
        points = 0
        if id in self._fruits:
            points = self._fruits[id].points
            self._fruits[id].remove()
        return points

    def remove_all(self):
        points = 0
        for id in self._fruits:
            points += self.remove(id)
        self.cleanup()
        return points

    def remove_next(self):
        if( self._next_fruit ):
            self._next_fruit.remove()
            self._next_fruit = None


    def spawn(self, kind, position):
        f =  Fruit( space=self._space,
                    kind=kind,
                    position=position,
                    on_remove=self.on_remove)
        self.add(f)
        f.fade_in()
        return f

    def on_remove(self, f):
        self._score += f.points

    def explose_seq(self, dt):
        """Makes the fruits explode, starting with the most recent one."""  
        # Searches for the oldest non-exploded fruit  
        explosables = [ i for i,f in self._fruits.items() if f._fruit_mode in [MODE_NORMAL, MODE_FIRST_DROP] ]
        if( explosables ):
            explosables.sort(reverse=True )
            self._fruits[explosables[0]].explose()
        # Finds the oldest non-exploded fruit  
        # Continues as long as there are fruits remaining  
        if( self._fruits ):
            pg.clock.schedule_once( self.explose_seq, GAMEOVER_ANIMATION_INTERVAL )

    def gameover(self):
        self._is_gameover = True
        self.remove_next()
        # program the explosion of remaining fruits
        print( f'Programming final explosion for {len(self._fruits)} active fruits')
        pg.clock.schedule_once( self.explose_seq, GAMEOVER_ANIMATION_START)

    def add(self, newfruit):
        self._fruits[ newfruit.id ] = newfruit

    def cleanup(self, all_fruits=False):
        """ garbage collection 
        """
        # remove fruits that have left the game
        for f in self._fruits.values():
            if not f.removed and f.is_offscreen():
                print( f"WARNING: {f} has left the game" )
                f.remove()

        # Removes references to REMOVED fruits (for garbage collection)  
        removed = [f.id for f in self._fruits.values() if (all_fruits or f.removed) ]
        for id in removed:
            del self._fruits[id]        # should trigger fruit.__del__()


    def _next_position(self):
        return ( self._window_size[0] // 2, 
                 self._window_size[1] - NEXT_FRUIT_Y_POS )

    def on_resize(self, width, height):
        self._window_size = (width, height)
        if( self._next_fruit ):
            self._next_fruit.position = self._next_position()