import time, sys
from random import randint, uniform
from typing import overload
import pygame
from pygame import gfxdraw
from pygame import Vector2 as V, Rect as R, Color as C
from pygame.locals import *
import pyfxr

class SpatialHash:
    def __init__(s, size):
        s.grid = {}
        s.size = size

    def insert(s, obj):
        x1 = obj.rect.x // s.size
        y1 = obj.rect.y // s.size
        x2 = obj.rect.right // s.size
        y2 = obj.rect.bottom // s.size
        obj.grid = []
        for x in range(x1, x2 + 1):
            for y in range(y1, y2 + 1):
                items = s.grid.get((x, y))
                if items is None:
                    s.grid[(x, y)] = [obj]
                else:
                    items.append(obj)
                obj.grid.append((x, y))

    def query(s, rect):
        x1 = rect.x // s.size
        y1 = rect.y // s.size
        x2 = rect.right // s.size
        y2 = rect.bottom // s.size    
        items = []
        for x in range(x1, x2 + 1):
            for y in range(y1, y2 + 1):
                items.extend(s.grid.get((x, y), ()))
        return items

    def draw(s):
        for g in s.grid:
            pygame.draw.rect(PDS, BLUE, (V(g) * s.size, (s.size, s.size)), 1)

class ball:
    def __init__(s, location):
        s.pos = V(location)
        s.vel = V()
        s.stopped = True

    def rect(s):
        return R(s.pos - (BALL_RADIUS, BALL_RADIUS), (BALL_RADIUS * 2, BALL_RADIUS * 2))

    def update(s):
        s.pos += s.vel * dt

        if s.vel.x != 0 or s.vel.y != 0:
            n_vel = s.vel.normalize()
            s.vel -= (s.vel * 0.01) * dt #(n_vel / FRICTION) * dt

        if round(s.vel.x + s.vel.y, 1) == 0:
            s.stopped = True

        if s.pos.x > PDR.w:
            s.pos.x = PDR.w
            s.vel.x = -s.vel.x
        if s.pos.x < 0:
            s.pos.x = 0
            s.vel.x = -s.vel.x
        if s.pos.y > PDR.h:
            s.pos.y = PDR.h
            s.vel.y = -s.vel.y
        if s.pos.y < 0:
            s.pos.y = 0
            s.vel.y = -s.vel.y
        
        _bumpers = SPATIAL.query(s.rect())
        for _bumper in _bumpers:
            if s.pos.distance_to(_bumper.pos) < BALL_RADIUS + BUMPER_RADIUS and _bumper.dead == False:
                relative_pos = s.pos - _bumper.pos
                angle = V().angle_to(relative_pos)
                s.pos = _bumper.pos + V(1, 0).rotate(angle) * (BALL_RADIUS + BUMPER_RADIUS + 1)
                s.vel.reflect_ip(_bumper.pos - s.pos)
                _bumper.dying = True
                _bumper.dying_start = time.perf_counter()
                BUMP.play()
                _bumper.bump_count += 1
                SCORE.increment()
                if _bumper.bump_count == 4:
                    BONUS.play()
                    SCORE.bonus()

    def draw(s):
        pygame.draw.circle(PDS, PALETTE[6], s.pos, BALL_RADIUS)

class bumper:
    def __init__(s):
        s.pos = V(randint(0, PDR.w), randint(0, PDR.h))
        s.rect = R(s.pos - V(BUMPER_RADIUS), V(BUMPER_RADIUS) * 2)
        s.dead = False
        s.dying = False
        s.dying_start = None
        s.dying_alpha = 255
        s.dying_radius = BUMPER_RADIUS
        s.bump_count = 0

    def overlap(s, bumper):
        if s.pos.distance_to(bumper.pos) <= BUMPER_RADIUS * 2 + 10:
            return True
        else:
            return False

    def update(s):
        if s.dying and not s.dead:
            time_since_hit = time.perf_counter() - s.dying_start
            if time_since_hit >= BUMPER_DYING_TIME:
                s.dead = True
                return            
            
            tsh_percent = time_since_hit / BUMPER_DYING_TIME

            s.dying_alpha = int(255 - V().lerp((255, 0), tsh_percent).x)
            s.dying_radius = int(BUMPER_RADIUS + V().lerp((BUMPER_MAX_DYING_SIZE, 0), tsh_percent).x)

    def draw(s):
        if s.dying:
            pygame.gfxdraw.filled_circle(PDS, int(s.pos.x), int(s.pos.y), s.dying_radius, PALETTE[2][:-1] + (s.dying_alpha,))
        pygame.draw.circle(PDS, PALETTE[3], s.pos, BUMPER_RADIUS)

class bumpers:
    def __init__(s, exclusion_point, exclusion_radius, n_bumpers):
        s.container = []
        for _ in range(n_bumpers):
            while True:
                new_bumper = bumper()
                if exclusion_point.distance_to(new_bumper.pos) < exclusion_radius + BUMPER_RADIUS: continue
                _bumpers = SPATIAL.query(new_bumper.rect.inflate((BUMPER_RADIUS, BUMPER_RADIUS)))
                space_found = True
                for _bumper in _bumpers:
                    if new_bumper.overlap(_bumper):
                        space_found = False
                        break
                if not space_found: continue
                break
            s.container.append(new_bumper)
            SPATIAL.insert(new_bumper)
        
    def draw(s):
        for _bumper in s.container:
            if not _bumper.dead: _bumper.draw()

    def update(s):
        dead_bumpers = []
        for _bumper in s.container:
            _bumper.update()
            if _bumper.dead:
                dead_bumpers.append(_bumper)
        for _bumper in dead_bumpers:
            s.container.remove(_bumper)

class scores:
    class _score:
        def __init__(s, pos, value, color):
            s.pos = pos
            s.vy = 0

            s.ts = time.perf_counter()

            s.surface = FONT.render(str(value), True, color)
            s.size = s.surface.get_rect().size

            s.dead = False

        def update(s):
            s.pos.y -= s.vy * dt
            s.vy += 0.06 * dt
            if s.vy >= 4:
                s.dead = True
                return
            s.surface.set_alpha(255 - int(V().lerp((255, 0), s.vy / 4).x))

        def draw(s):
            PDS.blit(s.surface, s.pos)

    def __init__(s):
        s.score = 0
        s.update_surface()

        s.score_timestamp = None
        s.score_multiplier = 1

        s.scores = []

    def random_pos(s):
        return V(PDR.center) + V(1, 0).rotate(randint(0, 359)) * 70

    def update_surface(s):
        s.surface = FONT.render(str(s.score), True, PALETTE[2])
        s.surface_size = V(s.surface.get_rect().size)

    def bonus(s):
        s.score += BONUS_SCORE
        s.scores.append(s._score(s.random_pos(), BONUS_SCORE, PALETTE[7]))

    def increment(s):
        now = time.perf_counter()
        if now - (now if s.score_timestamp == None else s.score_timestamp) > SCORE_DURATION:
            s.score_multiplier = 1
        s.scores.append(s._score(s.random_pos(), s.score_multiplier, PALETTE[6]))
        s.score += s.score_multiplier
        s.update_surface()
        s.score_multiplier += 1
        
        s.score_timestamp = time.perf_counter()       

    def draw(s):
        PDS.blit(s.surface, V(PDR.center) - s.surface_size / 2)

    def update(s):
        dead_scores = []
        for score in s.scores:
            score.draw()
            score.update()
            if score.dead:
                dead_scores.append(score)
        for score in dead_scores:
            s.scores.remove(score)

def find_threshold(m,n):
    return 2.0*m/(n*(n-1))

def power_gauge(source, target):
    distance = source.distance_to(target)
    distance_copy = distance / 1
    threshold = find_threshold(distance, 8)
    
    vector = V(1, 0).rotate(V().angle_to(target - source))

    for index in range(8):
        pos = source + vector * distance
        pygame.draw.rect(PDS, PALETTE[4], (pos - (1, 1), (3, 3)))
        distance -= threshold * index
    return vector * (distance_copy / 20)

pygame.init()
PDR = R(0, 0, 1280, 720)
PDS = pygame.display.set_mode(PDR.size)
pygame.display.set_caption('PLINKO')

FPS = 120

FONT = pygame.font.Font("font.ttf", 30)

BUMP = pygame.mixer.Sound("plink.wav")
BONUS = pygame.mixer.Sound("bonus.wav")

WHITE = (255, 255, 255)
BLACK = (0, 0, 0)
RED = (255, 0, 0)
BLUE = (0, 0, 255)
#          0         1         2         3         4         5         6         7
PALETTE = [C('#0d2b45'), C('#203c56'), C('#544e68'), C('#8d697a'), C('#d08159'), C('#ffaa5e'), C('#ffd4a3'), C('#ffecd6')]

SP = SpatialHash(64)

FRICTION = 10
BALL_RADIUS = 20
BUMPER_RADIUS =  10
BUMPER_DYING_TIME = 0.3
BUMPER_MAX_DYING_SIZE = 30

SPATIAL = SpatialHash(64)
BALL =  ball(PDR.center)
BUMPERS = bumpers(BALL.pos, 150, 200)

TIMER_POS = V(PDR.center)
TIMER_DURATION = 120
TIMER_ANGLE = 360 / TIMER_DURATION
TIMER = [TIMER_POS + V(1, 0).rotate(-90 + TIMER_ANGLE * index) * 100 for index in range(TIMER_DURATION, -1, -1)]
TIMER.insert(0, TIMER_POS)

BONUS_SCORE = 500
SCORE_DURATION = 1.5
SCORE = scores()

dts = time.perf_counter()

start_timer = False
timer_counter = 0

exit_demo = False
while not exit_demo:
    for e in pygame.event.get():
        if e.type == KEYUP and e.key == K_ESCAPE:
            exit_demo = True
    
    now = time.perf_counter()
    dt = (now - dts) * FPS
    dts = now

    if start_timer:
        timer_counter += dt
        if timer_counter > 100:
            timer_counter -= 100
            TIMER.pop()
            if len(TIMER) == 2: 
                break

    BALL.update()
    BUMPERS.update()

    PDS.fill(PALETTE[0])

    pygame.gfxdraw.filled_polygon(PDS, TIMER, PALETTE[1][:-1] + (64, ))
    pygame.draw.circle(PDS, PALETTE[0], TIMER_POS, 80)
    SCORE.draw()
    SCORE.update()

    BALL.draw()
    BUMPERS.draw()
    if BALL.stopped:
        power = power_gauge(BALL.pos, V(pygame.mouse.get_pos()))
        if pygame.mouse.get_pressed()[0]:
            BALL.stopped = False
            BALL.vel = power
            start_timer = True
            
    
    pygame.display.update()

pygame.image.save(PDS, "plinko_{}.png".format(SCORE.score))

pygame.quit()
sys.exit()