import pygame
import random
import math
import sys
import time
import json
import os

# 1. КОНСТАНТЫ

# Размер окна
SCREEN_W = 900
SCREEN_H = 700

# Игровое поле
COLS = 8
ROWS = 8
CELL_SIZE = 64          # пикселей на клетку
BOARD_OFF_X = 100         # отступ поля от левого края
BOARD_OFF_Y = 80          # отступ поля от верха

# FPS
FPS = 60

# Цветовая палитра UI
CLR_BG = (15,  12,  30)
CLR_BG2 = (22,  18,  45)
CLR_PANEL = (30,  24,  58)
CLR_ACCENT = (130, 80, 255)
CLR_ACCENT2 = (255, 180, 60)
CLR_TEXT = (230, 220, 255)
CLR_TEXT_DIM = (130, 120, 160)
CLR_BORDER = (60,  50, 100)
CLR_GRID = (35,  28,  65)

# Типы фишек: (имя, основной цвет, цвет блика)
GEM_TYPES = [
    ("ruby", (220,  50,  80), (255, 120, 140)),
    ("sapphire", ( 50, 100, 220), (100, 160, 255)),
    ("emerald", ( 40, 180,  80), (100, 240, 130)),
    ("gold", (220, 175,  30), (255, 220, 80 )),
    ("amethyst", (160,  50, 220), (210, 110, 255)),
    ("diamond", (160, 210, 230), (220, 245, 255)),
]
GEM_COUNT = len(GEM_TYPES)

# Время анимаций (секунды)
ANIM_SWAP_TIME = 0.18
ANIM_FALL_SPEED = 6.0   # клеток в секунду
ANIM_DESTROY_TIME = 0.30

# Очки
SCORE_BASE = 10   # за одну фишку
SCORE_COMBO = 1.5  # множитель за каждое следующее комбо

# Настройки сложности: (метка, время_таймера, очки_за_фишку_множитель)
DIFFICULTIES = {
    "Лёгкий": {"time": 90, "mult": 1.0},
    "Средний": {"time": 60, "mult": 1.5},
    "Сложный": {"time": 40, "mult": 2.5},
}

# Файл таблицы рекордов
SCORES_FILE = "gem_blitz_scores.json"

# 2. SOUND MANAGER — синтез звуков без внешних файлов

class SoundManager:
    """Генерирует все звуки программно и управляет их воспроизведением."""

    def __init__(self):
        self.enabled = True
        self.music_enabled = True
        pygame.mixer.init(frequency=44100, size=-16, channels=2, buffer=512)
        self.sounds = {}
        self._generate_sounds()
        self._start_music()

    # ── генерация ────────────────────────────────────────────────────────────

    def _make_tone(self, freq: float, duration: float,
                   volume: float = 0.4, wave: str = "sine",
                   decay: float = 1.0) -> pygame.mixer.Sound:
        """Создаёт звук заданной формы волны."""
        import numpy as np
        sample_rate = 44100
        n_samples = int(sample_rate * duration)
        t = np.linspace(0, duration, n_samples, endpoint=False)

        if wave == "sine":
            raw = np.sin(2 * math.pi * freq * t)
        elif wave == "square":
            raw = np.sign(np.sin(2 * math.pi * freq * t))
        elif wave == "sawtooth":
            raw = 2 * (t * freq - np.floor(0.5 + t * freq))
        else:
            raw = np.sin(2 * math.pi * freq * t)

        # огибающая: нарастание + спад
        env = np.exp(-decay * t / duration)
        raw = raw * env * volume

        # стерео int16
        data = (raw * 32767).astype(np.int16)
        stereo = np.column_stack([data, data])
        snd = pygame.sndarray.make_sound(stereo)
        return snd

    def _make_noise_burst(self, duration=0.15, volume=0.25) -> pygame.mixer.Sound:
        """Короткий шум для взрыва."""
        import numpy as np
        sample_rate = 44100
        n = int(sample_rate * duration)
        t = np.linspace(0, duration, n, endpoint=False)
        raw = np.random.uniform(-1, 1, n)
        env = np.exp(-8 * t / duration)
        raw = raw * env * volume
        data = (raw * 32767).astype(np.int16)
        stereo = np.column_stack([data, data])
        return pygame.sndarray.make_sound(stereo)

    def _make_chord(self, freqs, duration=0.4, volume=0.3, decay=3.0):
        """Создаёт аккорд из нескольких частот."""
        import numpy as np
        sample_rate = 44100
        n = int(sample_rate * duration)
        t = np.linspace(0, duration, n, endpoint=False)
        raw = np.zeros(n)
        for f in freqs:
            raw += np.sin(2 * math.pi * f * t)
        raw /= len(freqs)
        env = np.exp(-decay * t / duration)
        raw = raw * env * volume
        data = (raw * 32767).astype(np.int16)
        stereo = np.column_stack([data, data])
        return pygame.sndarray.make_sound(stereo)

    def _generate_sounds(self):
        """Инициализирует все игровые звуки."""
        try:
            import numpy as np
            self.sounds["click"]   = self._make_tone(440,  0.08, volume=0.3, wave="sine", decay=6)
            self.sounds["swap"]    = self._make_tone(660,  0.12, volume=0.3, wave="sine", decay=4)
            self.sounds["invalid"] = self._make_tone(200,  0.20, volume=0.3, wave="square", decay=3)
            self.sounds["match3"]  = self._make_chord([523, 659, 784], 0.35, volume=0.35, decay=3)
            self.sounds["match4"]  = self._make_chord([659, 784, 988], 0.40, volume=0.40, decay=2)
            self.sounds["match5"]  = self._make_chord([784, 988, 1175, 1319], 0.50, volume=0.45, decay=2)
            self.sounds["combo"]   = self._make_chord([1047, 1319, 1568], 0.45, volume=0.40, decay=2)
            self.sounds["explode"] = self._make_noise_burst(0.18, volume=0.30)
            self.sounds["gameover"]= self._make_chord([196, 233, 277], 1.20, volume=0.40, decay=1)

        except ImportError:  # numpy недоступен, поэтому звук будет отключён
            self.enabled = False
            self.music_enabled = False

    def _start_music(self):
        """Генерирует простую фоновую «музыку» — зацикленный аккорд."""
        if not self.music_enabled:
            return
        try:
            import numpy as np
            sample_rate = 44100
            bpm = 90
            bar = int(sample_rate * 4 * 60 / bpm)
            t = np.linspace(0, 4 * 60 / bpm, bar, endpoint=False)

            # Простая арпеджио-последовательность
            freqs_seq = [130.8, 164.8, 196.0, 246.9,
                         261.6, 196.0, 164.8, 130.8]
            beat_len = bar // len(freqs_seq)
            raw = np.zeros(bar)
            for i, f in enumerate(freqs_seq):
                start = i * beat_len
                end = start + beat_len
                seg_t = np.linspace(0, beat_len / sample_rate, beat_len, endpoint=False)
                tone = np.sin(2 * math.pi * f * seg_t) * 0.15
                tone += np.sin(2 * math.pi * f * 2 * seg_t) * 0.05
                env = np.exp(-3 * seg_t / (beat_len / sample_rate))
                raw[start:end] = tone * env

            # Лёгкий реверб (простое эхо)
            delay = int(sample_rate * 0.25)
            echo  = np.zeros_like(raw)
            echo[delay:] = raw[:-delay] * 0.3
            raw = np.clip(raw + echo, -1, 1)

            data = (raw * 32767).astype(np.int16)
            stereo = np.column_stack([data, data])
            buf = stereo.tobytes()
            snd = pygame.mixer.Sound(buffer=buf)
            snd.set_volume(0.4)
            snd.play(loops=-1)
            self.music_sound = snd

        except Exception:
            self.music_enabled = False

    # ── интерфейс ────────────────────────────────────────────────────────────

    def play(self, name: str):
        if self.enabled and name in self.sounds:
            self.sounds[name].play()

    def toggle_sound(self):
        self.enabled = not self.enabled

    def toggle_music(self):
        self.music_enabled = not self.music_enabled
        if hasattr(self, "music_sound"):
            if self.music_enabled:
                self.music_sound.set_volume(0.4)
            else:
                self.music_sound.set_volume(0.0)

# 3. PARTICLE — частица взрыва

class Particle:
    """Одна частица взрыва при уничтожении фишки."""

    def __init__(self, x: float, y: float, color: tuple):
        angle = random.uniform(0, 2 * math.pi)
        speed = random.uniform(60, 220)
        self.x = x
        self.y = y
        self.vx = math.cos(angle) * speed
        self.vy = math.sin(angle) * speed - random.uniform(20, 80)
        self.r = random.randint(3, 7)
        self.color = color
        self.alpha = 255
        self.gravity = 350
        self.alive = True

    def update(self, dt: float):
        self.vy += self.gravity * dt
        self.x += self.vx * dt
        self.y += self.vy * dt
        self.alpha -= 600 * dt
        if self.alpha <= 0:
            self.alpha = 0
            self.alive = False

    def draw(self, surface: pygame.Surface):
        if not self.alive:
            return
        
        s = pygame.Surface((self.r * 2, self.r * 2), pygame.SRCALPHA)
        pygame.draw.circle(s, (*self.color, int(self.alpha)), (self.r, self.r), self.r)
        surface.blit(s, (int(self.x - self.r), int(self.y - self.r)))

# 4. GEM — фишка
class Gem:
    # Кэш поверхностей фишек (рисуем один раз)
    _cache: dict = {}

    def __init__(self, col: int, row: int, gem_type: int):
        self.col = col
        self.row = row
        self.gem_type  = gem_type
        self.px = float(BOARD_OFF_X + col * CELL_SIZE + CELL_SIZE // 2)
        self.py = float(BOARD_OFF_Y + row * CELL_SIZE + CELL_SIZE // 2)
        self.target_px = self.px
        self.target_py = self.py
        self.state = "idle"
        self.alpha = 255    # для fade-анимации смерти
        self.scale = 1.0   # для пульсации выделения
        self._sel_time = 0.0   # таймер пульсации выделения
        self.shake = 0.0   # горизонтальное дрожание при invalid

    # ── рисование ────────────────────────────────────────────────────────────

    @classmethod
    def _make_gem_surface(cls, gem_type: int, size: int) -> pygame.Surface:
        """Создаёт поверхность фишки заданного типа (кэшируется)."""
        key = (gem_type, size)

        if key in cls._cache:
            return cls._cache[key]

        name, color, hi_color = GEM_TYPES[gem_type]
        surf = pygame.Surface((size, size), pygame.SRCALPHA)
        cx, cy = size // 2, size // 2
        r  = size // 2 - 4

        # Фигура зависит от типа
        if gem_type == 0:   # ruby — круг
            pygame.draw.circle(surf, color,    (cx, cy), r)
            pygame.draw.circle(surf, hi_color, (cx - r//3, cy - r//3), r//3)
            pygame.draw.circle(surf, (255,255,255,200), (cx, cy), r, 2)
        elif gem_type == 1: # sapphire — ромб
            pts = [(cx, cy-r), (cx+r, cy), (cx, cy+r), (cx-r, cy)]
            pygame.draw.polygon(surf, color,    pts)
            pygame.draw.polygon(surf, hi_color, [(cx, cy-r//2), (cx+r//3, cy-r//4),
                                                  (cx, cy), (cx-r//3, cy-r//4)])
            pygame.draw.polygon(surf, (255,255,255,200), pts, 2)
        elif gem_type == 2: # emerald — шестиугольник
            pts = []

            for i in range(6):
                a = math.radians(60 * i - 30)
                pts.append((cx + r * math.cos(a), cy + r * math.sin(a)))
            pygame.draw.polygon(surf, color, pts)
            pygame.draw.polygon(surf, hi_color, [(cx, cy-r//2), (cx+r//3, cy-r//4),
                                                  (cx+r//3, cy+r//4), (cx, cy+r//2),
                                                  (cx-r//3, cy+r//4), (cx-r//3, cy-r//4)])
            pygame.draw.polygon(surf, (255,255,255,200), pts, 2)
        elif gem_type == 3: # gold — квадрат с закруглением
            rect = pygame.Rect(cx-r, cy-r, r*2, r*2)
            pygame.draw.rect(surf, color,    rect, border_radius=8)
            pygame.draw.rect(surf, hi_color, pygame.Rect(cx-r//2, cy-r//2, r, r//2), border_radius=4)
            pygame.draw.rect(surf, (255,255,255,200), rect, 2, border_radius=8)
        elif gem_type == 4: # amethyst — звезда
            pts = []

            for i in range(10):
                a = math.radians(36 * i - 90)
                rad = r if i % 2 == 0 else r // 2
                pts.append((cx + rad * math.cos(a), cy + rad * math.sin(a)))
            pygame.draw.polygon(surf, color,    pts)
            pygame.draw.polygon(surf, (255,255,255,200), pts, 2)
        else:               # diamond — восьмиугольник
            pts = []

            for i in range(8):
                a = math.radians(45 * i)
                pts.append((cx + r * math.cos(a), cy + r * math.sin(a)))
            pygame.draw.polygon(surf, color,    pts)
            pygame.draw.polygon(surf, hi_color, [(cx-r//3, cy-r//3), (cx+r//3, cy-r//3),
                                                  (cx+r//4, cy), (cx-r//4, cy)])
            pygame.draw.polygon(surf, (255,255,255,200), pts, 2)

        cls._cache[key] = surf
        return surf

    def draw(self, surface: pygame.Surface, selected: bool = False):
        if self.state == "dying" and self.alpha <= 0:
            return

        size = CELL_SIZE - 8
        base = self._make_gem_surface(self.gem_type, size)

        # Масштабирование (выделение / смерть)
        sc = self.scale
        if self.state == "dying":
            sc = max(0.0, self.alpha / 255.0)
        draw_size = max(2, int(size * sc))

        scaled = pygame.transform.smoothscale(base, (draw_size, draw_size))

        # Прозрачность
        alpha = self.alpha if self.state == "dying" else 255
        if selected:
            # Белое свечение вокруг
            glow_size = draw_size + 12
            glow = pygame.Surface((glow_size, glow_size), pygame.SRCALPHA)
            glow_alpha = int(120 + 80 * math.sin(self._sel_time * 6))
            pygame.draw.circle(glow, (*GEM_TYPES[self.gem_type][2], glow_alpha),
                                (glow_size // 2, glow_size // 2), glow_size // 2)
            surface.blit(glow,
                         (int(self.px - glow_size // 2 + self.shake),
                          int(self.py - glow_size // 2)))

        if alpha < 255:
            scaled.set_alpha(alpha)

        draw_x = int(self.px - draw_size // 2 + self.shake)
        draw_y = int(self.py - draw_size // 2)
        surface.blit(scaled, (draw_x, draw_y))

    # ── обновление ───────────────────────────────────────────────────────────

    def update(self, dt: float) -> bool:
        """Возвращает True, если анимация завершена."""
        self._sel_time += dt

        if self.state == "swapping" or self.state == "falling":
            # Движение к цели
            dx = self.target_px - self.px
            dy = self.target_py - self.py
            dist = math.hypot(dx, dy)

            if dist < 2:
                self.px, self.py = self.target_px, self.target_py
                self.state = "idle"
                return True
            
            speed = CELL_SIZE * (7 if self.state == "swapping" else ANIM_FALL_SPEED)
            step  = speed * dt

            if step >= dist:
                self.px, self.py = self.target_px, self.target_py
                self.state = "idle"
                return True
            
            self.px += dx / dist * step
            self.py += dy / dist * step

        elif self.state == "dying":
            self.alpha -= 255 / ANIM_DESTROY_TIME * dt
            self.scale  = max(0.0, self.alpha / 255.0 * 1.4)
            if self.alpha <= 0:
                return True

        elif self.state == "shaking":
            self.shake  = math.sin(self._sel_time * 40) * 5 * max(0, 1 - self._sel_time / 0.3)
            if self._sel_time > 0.3:
                self.shake = 0
                self.state = "idle"

        return False

    def move_to(self, col: int, row: int):
        """Задаёт новую логическую позицию и запускает анимацию движения."""
        self.col = col
        self.row = row
        self.target_px = float(BOARD_OFF_X + col * CELL_SIZE + CELL_SIZE // 2)
        self.target_py = float(BOARD_OFF_Y + row * CELL_SIZE + CELL_SIZE // 2)

    def snap_to(self, col: int, row: int):
        """Мгновенно устанавливает позицию без анимации."""
        self.col = col
        self.row = row
        self.px = float(BOARD_OFF_X + col * CELL_SIZE + CELL_SIZE // 2)
        self.py = float(BOARD_OFF_Y + row * CELL_SIZE + CELL_SIZE // 2)
        self.target_px = self.px
        self.target_py = self.py

    def start_dying(self):
        self.state = "dying"
        self.alpha = 255.0
        self.scale = 1.0

    def start_shaking(self):
        self.state = "shaking"
        self._sel_time = 0.0

# 5. BOARD — игровое поле
class Board:
    def __init__(self, sound: SoundManager, score_mult: float = 1.0):
        self.sound = sound
        self.score_mult = score_mult
        self.grid: list[list[Gem | None]] = [[None] * COLS for _ in range(ROWS)]
        self.particles: list[Particle] = []
        self.state = "idle"
        self.selected: tuple[int, int] | None = None   # (col, row)
        self.score_delta = 0   # очки за последний ход (передаются в Game)
        self.combo = 0
        self._swap_a: tuple[int, int] | None = None
        self._swap_b: tuple[int, int] | None = None
        self._dying_gems: list[Gem] = []
        self._valid_swap = True

        self._fill_board()
        self._clear_initial_matches()

    # ── инициализация ─────────────────────────────────────────────────────────

    def _fill_board(self):
        """Заполняет поле случайными фишками."""
        for row in range(ROWS):
            for col in range(COLS):
                gem_type = random.randint(0, GEM_COUNT - 1)
                g = Gem(col, row, gem_type)
                self.grid[row][col] = g

    def _clear_initial_matches(self):
        """Убирает совпадения с начального поля, меняя типы фишек."""
        for row in range(ROWS):
            for col in range(COLS):
                while True:
                    matches = self._check_gem_matches(col, row)
                    if not matches:
                        break

                    types = list(range(GEM_COUNT))
                    random.shuffle(types)

                    for t in types:
                        self.grid[row][col].gem_type = t
                        if not self._check_gem_matches(col, row):
                            break

    def _check_gem_matches(self, col: int, row: int) -> list:
        """Проверяет, входит ли фишка (col,row) в горизонтальное/вертикальное совпадение."""
        g = self.grid[row][col]
        if g is None:
            return []
        
        t = g.gem_type
        result = []
        # горизонталь
        run = [col]
        c = col - 1

        while c >= 0 and self.grid[row][c] and self.grid[row][c].gem_type == t:
            run.insert(0, c); c -= 1

        c = col + 1

        while c < COLS and self.grid[row][c] and self.grid[row][c].gem_type == t:
            run.append(c); c += 1

        if len(run) >= 3:
            result.extend([(c2, row) for c2 in run])
        # вертикаль
        run = [row]
        r = row - 1

        while r >= 0 and self.grid[r][col] and self.grid[r][col].gem_type == t:
            run.insert(0, r); r -= 1

        r = row + 1

        while r < ROWS and self.grid[r][col] and self.grid[r][col].gem_type == t:
            run.append(r); r += 1

        if len(run) >= 3:
            result.extend([(col, r2) for r2 in run])
        return result

    # ── публичный интерфейс ───────────────────────────────────────────────────

    def click(self, px: int, py: int):
        """Обрабатывает клик мыши по полю."""
        if self.state != "idle":
            return
        
        col = (px - BOARD_OFF_X) // CELL_SIZE
        row = (py - BOARD_OFF_Y) // CELL_SIZE
        if not (0 <= col < COLS and 0 <= row < ROWS):
            self.selected = None
            return

        self.sound.play("click")

        if self.selected is None:
            self.selected = (col, row)
        else:
            sc, sr = self.selected

            # Проверяем соседство
            if abs(sc - col) + abs(sr - row) == 1:
                self._begin_swap(sc, sr, col, row)
            else:
                # Перевыбираем
                self.selected = (col, row)

    def _begin_swap(self, c1, r1, c2, r2):
        """Запускает анимацию обмена двух фишек."""
        self.selected = None
        self._swap_a = (c1, r1)
        self._swap_b = (c2, r2)
        self.state = "swapping"
        self.combo = 0
        self.score_delta = 0

        ga = self.grid[r1][c1]
        gb = self.grid[r2][c2]
        ga.state = "swapping"
        gb.state = "swapping"
        ga.move_to(c2, r2)
        gb.move_to(c1, r1)
        self.sound.play("swap")

    def update(self, dt: float):
        """Обновляет все анимации и логику поля."""
        # Обновляем частицы
        for p in self.particles:
            p.update(dt)
        self.particles = [p for p in self.particles if p.alive]

        if self.state == "idle":
            # Обновляем пульсацию выбранной фишки
            if self.selected:
                sc, sr = self.selected
                g = self.grid[sr][sc]

                if g:
                    g._sel_time += dt
            return

        elif self.state == "swapping":
            # Ждём завершения анимации обмена обоих
            c1, r1 = self._swap_a
            c2, r2 = self._swap_b
            ga = self.grid[r1][c1]
            gb = self.grid[r2][c2]
            done_a = ga.update(dt) if ga.state == "swapping" else True
            done_b = gb.update(dt) if gb.state == "swapping" else True

            if done_a and done_b:
                # Физически меняем в сетке
                self.grid[r1][c1], self.grid[r2][c2] = self.grid[r2][c2], self.grid[r1][c1]
                # Корректируем логические координаты
                if self.grid[r1][c1]: 
                    self.grid[r1][c1].col, self.grid[r1][c1].row = c1, r1
                if self.grid[r2][c2]: 
                    self.grid[r2][c2].col, self.grid[r2][c2].row = c2, r2

                self.state = "checking"
                self._valid_swap = True

        elif self.state == "checking":
            matches = self._find_all_matches()

            if matches:
                self._start_dying(matches)
            else:
                if self.combo == 0:
                    # Не было совпадений — откат
                    self._valid_swap = False
                    self._revert_swap()
                else:
                    self.state = "done"

        elif self.state == "dying":
            # Ждём завершения анимации смерти
            all_done = True

            for g in self._dying_gems:
                done = g.update(dt)
                if not done:
                    all_done = False
            if all_done:
                self._dying_gems.clear()
                self._apply_gravity()
                self.state = "falling"

        elif self.state == "falling":
            # Ждём завершения анимации падения
            all_done = True
            for row in range(ROWS):
                for col in range(COLS):
                    g = self.grid[row][col]
                    if g and g.state == "falling":
                        done = g.update(dt)
                        if not done:
                            all_done = False
            if all_done:
                self.state = "checking"  # комбо-цепочка

        # Обновляем idle-фишки (пульсация выбранной)
        if self.state == "idle" and self.selected:
            sc, sr = self.selected
            g = self.grid[sr][sc]
            if g:
                g._sel_time += dt

    # ── логика совпадений ─────────────────────────────────────────────────────

    def _find_all_matches(self) -> set:
        """Находит все совпадения на поле. Возвращает set[(col, row)]."""
        matched = set()
        for row in range(ROWS):
            col = 0

            while col < COLS - 2:
                g = self.grid[row][col]
                if g:
                    run = [col]
                    c = col + 1
                    while c < COLS and self.grid[row][c] and \
                          self.grid[row][c].gem_type == g.gem_type:
                        run.append(c); c += 1
                    if len(run) >= 3:
                        for x in run:
                            matched.add((x, row))
                    col = c
                else:
                    col += 1
        for col in range(COLS):
            row = 0

            while row < ROWS - 2:
                g = self.grid[row][col]

                if g:
                    run = [row]
                    r = row + 1
                    while r < ROWS and self.grid[r][col] and \
                          self.grid[r][col].gem_type == g.gem_type:
                        run.append(r); r += 1

                    if len(run) >= 3:
                        for y in run:
                            matched.add((col, y))
                    row = r
                else:
                    row += 1
        return matched

    def _start_dying(self, matches: set):
        """Запускает анимацию уничтожения для совпавших фишек."""
        self.combo += 1
        count = len(matches)

        # Звук зависит от размера совпадения и комбо
        if self.combo > 1:
            self.sound.play("combo")
        elif count >= 5:
            self.sound.play("match5")
        elif count >= 4:
            self.sound.play("match4")
        else:
            self.sound.play("match3")
        self.sound.play("explode")

        # Начисляем очки
        pts = count * SCORE_BASE * self.score_mult * (SCORE_COMBO ** (self.combo - 1))
        self.score_delta += int(pts)

        for (col, row) in matches:
            g = self.grid[row][col]

            if g and g.state != "dying":
                g.start_dying()
                self._dying_gems.append(g)
                # Создаём частицы
                _, clr, hi = GEM_TYPES[g.gem_type]

                for _ in range(random.randint(6, 12)):
                    self.particles.append(Particle(g.px, g.py, clr))

                for _ in range(3):
                    self.particles.append(Particle(g.px, g.py, hi))

        self.state = "dying"

    def _apply_gravity(self):
        """Убирает мёртвые фишки, сдвигает оставшиеся вниз, добавляет новые."""
        # Убираем мёртвые
        for row in range(ROWS):
            for col in range(COLS):
                g = self.grid[row][col]
                if g and g.state == "dying":
                    self.grid[row][col] = None

        # Сдвигаем вниз по каждой колонке
        for col in range(COLS):
            column = [self.grid[row][col] for row in range(ROWS)]
            filled = [g for g in column if g is not None]
            empty = ROWS - len(filled)
            # Новые фишки появляются сверху (за кадром)
            for i in range(empty):
                gt = random.randint(0, GEM_COUNT - 1)
                g  = Gem(col, -1 - i, gt)
                # Стартовая пиксельная позиция выше экрана
                g.px = float(BOARD_OFF_X + col * CELL_SIZE + CELL_SIZE // 2)
                g.py = float(BOARD_OFF_Y + (-1 - i) * CELL_SIZE + CELL_SIZE // 2)
                filled.insert(0, g)

            # Расставляем в сетке и запускаем падение
            for row in range(ROWS):
                g = filled[row]
                target_py = float(BOARD_OFF_Y + row * CELL_SIZE + CELL_SIZE // 2)

                if abs(g.py - target_py) > 2:
                    g.col = col
                    g.row = row
                    g.target_px = float(BOARD_OFF_X + col * CELL_SIZE + CELL_SIZE // 2)
                    g.target_py = target_py
                    g.state = "falling"
                else:
                    g.snap_to(col, row)
                self.grid[row][col] = g

    def _revert_swap(self):
        """Откатывает некорректный обмен назад."""
        c1, r1 = self._swap_a
        c2, r2 = self._swap_b
        ga = self.grid[r1][c1]
        gb = self.grid[r2][c2]
        # В сетке они уже поменялись местами — возвращаем
        self.grid[r1][c1], self.grid[r2][c2] = self.grid[r2][c2], self.grid[r1][c1]

        if self.grid[r1][c1]: 
            self.grid[r1][c1].snap_to(c1, r1)
        if self.grid[r2][c2]: 
            self.grid[r2][c2].snap_to(c2, r2)
        # Анимация дрожания
        if ga: 
            ga.start_shaking()
        if gb: 
            gb.start_shaking()

        self.sound.play("invalid")
        self.state = "done"

    # ── отрисовка ─────────────────────────────────────────────────────────────

    def draw(self, surface: pygame.Surface):
        """Рисует поле, фишки и частицы."""
        self._draw_grid(surface)
        self._draw_gems(surface)
        for p in self.particles:
            p.draw(surface)

    def _draw_grid(self, surface: pygame.Surface):
        """Рисует подложку игрового поля."""
        for row in range(ROWS):
            for col in range(COLS):
                x = BOARD_OFF_X + col * CELL_SIZE
                y = BOARD_OFF_Y + row * CELL_SIZE
                clr = CLR_GRID if (row + col) % 2 == 0 else CLR_BG2
                pygame.draw.rect(surface, clr, (x, y, CELL_SIZE, CELL_SIZE))
                pygame.draw.rect(surface, CLR_BORDER, (x, y, CELL_SIZE, CELL_SIZE), 1)

        # Рамка поля
        bw = COLS * CELL_SIZE
        bh = ROWS * CELL_SIZE
        pygame.draw.rect(surface, CLR_ACCENT,
                         (BOARD_OFF_X - 2, BOARD_OFF_Y - 2, bw + 4, bh + 4), 2)

    def _draw_gems(self, surface: pygame.Surface):
        """Рисует все фишки."""
        sel = self.selected
        for row in range(ROWS):
            for col in range(COLS):
                g = self.grid[row][col]

                if g:
                    is_sel = (sel is not None and sel == (col, row))
                    # Обновляем idle-анимацию (пульсация выделения)
                    if g.state not in ("swapping", "falling", "dying", "shaking"):
                        pass  # уже обновлено в update()

                    g.draw(surface, selected=is_sel)
        # Dying gems поверх всего
        for g in self._dying_gems:
            if g.state == "dying":
                g.draw(surface)

    # ── вспомогательное ──────────────────────────────────────────────────────

    def is_busy(self) -> bool:
        """True, если поле в процессе анимации."""
        return self.state not in ("idle", "done")

    def consume_score(self) -> int:
        """Забирает накопленные очки и сбрасывает счётчик."""
        s = self.score_delta
        self.score_delta = 0
        if self.state == "done":
            self.state = "idle"
        return s

# 6. BUTTON — UI-кнопка
class Button:
    """Простая прямоугольная кнопка с hover-эффектом."""
    def __init__(self, x: int, y: int, w: int, h: int,
                 text: str, font: pygame.font.Font,
                 color=CLR_ACCENT, text_color=CLR_TEXT,
                 border_radius: int = 12):
        self.rect = pygame.Rect(x, y, w, h)
        self.text = text
        self.font = font
        self.color = color
        self.text_color  = text_color
        self.border_radius = border_radius
        self.hovered = False
        self._anim = 0.0   # 0..1 для hover-анимации

    def update(self, dt: float, mouse_pos: tuple):
        self.hovered = self.rect.collidepoint(mouse_pos)
        target = 1.0 if self.hovered else 0.0
        self._anim += (target - self._anim) * min(1, dt * 10)

    def draw(self, surface: pygame.Surface):
        # Фон с hover-осветлением
        t = self._anim
        base = self.color
        hi = tuple(min(255, int(c + 40 * t)) for c in base)
        pygame.draw.rect(surface, hi, self.rect, border_radius=self.border_radius)
        # Обводка
        pygame.draw.rect(surface, tuple(min(255, c + 80) for c in base),
                         self.rect, 2, border_radius=self.border_radius)
        # Текст
        txt = self.font.render(self.text, True, self.text_color)
        surface.blit(txt, txt.get_rect(center=self.rect.center))

    def is_clicked(self, event: pygame.event.Event) -> bool:
        return (event.type == pygame.MOUSEBUTTONDOWN and
                event.button == 1 and
                self.rect.collidepoint(event.pos))

# 7. GAME — главный класс

class Game:
    def __init__(self):
        pygame.init()
        self.screen = pygame.display.set_mode((SCREEN_W, SCREEN_H))
        pygame.display.set_caption("Gem Blitz ✦ Match-3")

        self.clock = pygame.time.Clock()
        self.sound = SoundManager()

        # Шрифты
        self.font_title = pygame.font.SysFont("Arial", 52, bold=True)
        self.font_large = pygame.font.SysFont("Arial", 36, bold=True)
        self.font_medium = pygame.font.SysFont("Arial", 26)
        self.font_small = pygame.font.SysFont("Arial", 20)

        # Состояние
        self.state = "menu"
        self.difficulty = "Средний"
        self.score = 0
        self.time_left = 60.0
        self.board: Board | None = None
        self.high_scores: list[dict] = self._load_scores()

        # Фоновые звёзды
        self.stars = [(random.randint(0, SCREEN_W), random.randint(0, SCREEN_H),
                       random.uniform(0.5, 2.0), random.uniform(0, 6.28))
                      for _ in range(120)]

        # Время
        self._prev_time = time.time()

        self._build_menu_buttons()

    # ── постоянные UI-кнопки ──────────────────────────────────────────────────

    def _build_menu_buttons(self):
        cx = SCREEN_W // 2
        w, h = 260, 56
        self.btn_play = Button(cx - w//2, 280, w, h, "▶  Играть", self.font_medium)
        self.btn_scores = Button(cx - w//2, 360, w, h, "🏆  Рекорды", self.font_medium, color=(80, 60, 160))
        self.btn_quit = Button(cx - w//2, 440, w, h, "✕  Выход", self.font_medium, color=(120, 40, 60))

        # Кнопки сложности
        diffs = list(DIFFICULTIES.keys())
        bw = 200
        gap = 20
        total = len(diffs) * bw + (len(diffs)-1) * gap
        sx = cx - total // 2
        self.btn_diffs = {}

        for i, d in enumerate(diffs):
            self.btn_diffs[d] = Button(sx + i*(bw+gap), 340, bw, 56, d, self.font_medium,
                                        color=(80, 55, 180))
        self.btn_back = Button(cx - 100, 500, 200, 48, "← Назад", self.font_medium,
                               color=(60, 50, 110))

        # Кнопки в игре (правая панель)
        rx = BOARD_OFF_X + COLS * CELL_SIZE + 30
        self.btn_snd = Button(rx, 300, 160, 44, "🔊 Звук", self.font_small, color=(60,50,110))
        self.btn_music = Button(rx, 360, 160, 44, "🎵 Музыка", self.font_small, color=(60,50,110))
        self.btn_menu  = Button(rx, 430, 160, 44, "☰ Меню", self.font_small, color=(80,40,80))

        # Кнопки game over
        self.btn_again = Button(cx - 130, 440, 260, 56, "▶  Играть снова", self.font_medium)
        self.btn_gmenu = Button(cx - 130, 520, 260, 56, "☰  Главное меню", self.font_medium, color=(60,50,110))

        # Кнопка возврата из рекордов
        self.btn_scores_back = Button(cx - 100, 580, 200, 48, "← Назад", self.font_medium,
                                       color=(60,50,110))

    # ── главный цикл ─────────────────────────────────────────────────────────

    def run(self):
        while True:
            now = time.time()
            dt  = min(now - self._prev_time, 0.05)
            self._prev_time = now

            events = pygame.event.get()

            for e in events:
                if e.type == pygame.QUIT:
                    pygame.quit()
                    sys.exit()

                self._handle_event(e)

            self._update(dt)
            self._draw()

            pygame.display.flip()
            self.clock.tick(FPS)

    # ── обработка событий ─────────────────────────────────────────────────────

    def _handle_event(self, e: pygame.event.Event):
        mp = pygame.mouse.get_pos()

        if self.state == "menu":
            if self.btn_play.is_clicked(e):
                self.sound.play("click")
                self.state = "difficulty"
            elif self.btn_scores.is_clicked(e):
                self.sound.play("click")
                self.state = "scores"
            elif self.btn_quit.is_clicked(e):
                pygame.quit()
                sys.exit()

        elif self.state == "difficulty":
            for name, btn in self.btn_diffs.items():
                if btn.is_clicked(e):
                    self.sound.play("click")
                    self.difficulty = name
                    self._start_game()
            if self.btn_back.is_clicked(e):
                self.sound.play("click")
                self.state = "menu"

        elif self.state == "playing":
            if e.type == pygame.MOUSEBUTTONDOWN and e.button == 1:
                mx, my = e.pos
                # Клик по полю
                bx = BOARD_OFF_X
                by = BOARD_OFF_Y
                bw = COLS * CELL_SIZE
                bh = ROWS * CELL_SIZE
                if bx <= mx < bx + bw and by <= my < by + bh:
                    if self.board:
                        self.board.click(mx, my)

            if self.btn_snd.is_clicked(e):
                self.sound.toggle_sound()

            if self.btn_music.is_clicked(e):
                self.sound.toggle_music()

            if self.btn_menu.is_clicked(e):
                self.sound.play("click")
                self.state = "menu"

        elif self.state == "gameover":
            if self.btn_again.is_clicked(e):
                self.sound.play("click")
                self._start_game()

            if self.btn_gmenu.is_clicked(e):
                self.sound.play("click")
                self.state = "menu"

        elif self.state == "scores":
            if self.btn_scores_back.is_clicked(e):
                self.sound.play("click")
                self.state = "menu"

    # ── обновление ────────────────────────────────────────────────────────────

    def _update(self, dt: float):
        mp = pygame.mouse.get_pos()

        if self.state == "menu":
            self.btn_play.update(dt, mp)
            self.btn_scores.update(dt, mp)
            self.btn_quit.update(dt, mp)

        elif self.state == "difficulty":
            for btn in self.btn_diffs.values():
                btn.update(dt, mp)
            self.btn_back.update(dt, mp)

        elif self.state == "playing":
            self.btn_snd.update(dt, mp)
            self.btn_music.update(dt, mp)
            self.btn_menu.update(dt, mp)

            # Таймер
            self.time_left -= dt

            if self.time_left <= 0:
                self.time_left = 0
                self._end_game()
                return

            # Поле
            if self.board:
                self.board.update(dt)
                pts = self.board.consume_score()
                self.score += pts

        elif self.state == "gameover":
            self.btn_again.update(dt, mp)
            self.btn_gmenu.update(dt, mp)

        elif self.state == "scores":
            self.btn_scores_back.update(dt, mp)

        # Анимация звёзд
        for i, (x, y, spd, phase) in enumerate(self.stars):
            phase = (phase + dt * spd * 0.5) % (2 * math.pi)
            self.stars[i] = (x, y, spd, phase)

    # ── запуск / конец игры ───────────────────────────────────────────────────

    def _start_game(self):
        cfg = DIFFICULTIES[self.difficulty]
        self.time_left = float(cfg["time"])
        self.score = 0
        self.board = Board(self.sound, score_mult=cfg["mult"])
        self.state = "playing"

    def _end_game(self):
        self.sound.play("gameover")
        # Сохраняем рекорд
        self.high_scores.append({
            "score": self.score,
            "difficulty": self.difficulty,
        })
        self.high_scores.sort(key=lambda x: x["score"], reverse=True)
        self.high_scores = self.high_scores[:10]
        self._save_scores()
        self.state = "gameover"

    # ── отрисовка ─────────────────────────────────────────────────────────────

    def _draw(self):
        self.screen.fill(CLR_BG)
        self._draw_stars()

        if self.state == "menu":
            self._draw_menu()
        elif self.state == "difficulty":
            self._draw_difficulty()
        elif self.state == "playing":
            self._draw_playing()
        elif self.state == "gameover":
            self._draw_gameover()
        elif self.state == "scores":
            self._draw_scores()

    def _draw_stars(self):
        """Рисует анимированное звёздное небо на фоне."""
        t = time.time()
        for (x, y, spd, phase) in self.stars:
            brightness = int(80 + 80 * math.sin(phase))
            r = max(1, int(spd * 0.7))
            pygame.draw.circle(self.screen, (brightness, brightness, brightness + 40), (x, y), r)

    def _draw_title(self, text: str, y: int, color=CLR_ACCENT):
        """Рисует заголовок с тенью."""
        shadow = self.font_title.render(text, True, (0, 0, 0))
        title = self.font_title.render(text, True, color)
        cx = SCREEN_W // 2
        self.screen.blit(shadow, shadow.get_rect(center=(cx + 3, y + 3)))
        self.screen.blit(title,  title.get_rect(center=(cx, y)))

    def _draw_menu(self):
        self._draw_title("✦ GEM BLITZ ✦", 140)
        sub = self.font_small.render("Собирай совпадения — бей рекорды!", True, CLR_TEXT_DIM)
        self.screen.blit(sub, sub.get_rect(center=(SCREEN_W//2, 200)))
        self.btn_play.draw(self.screen)
        self.btn_scores.draw(self.screen)
        self.btn_quit.draw(self.screen)

        # Декоративные фишки
        preview = [0, 1, 2, 3, 4, 5]
        for i, gt in enumerate(preview):
            cx = SCREEN_W // 2 - len(preview) * 22 + i * 44
            cy = 240
            surf = Gem._make_gem_surface(gt, 36)
            self.screen.blit(surf, (cx - 18, cy - 18))

    def _draw_difficulty(self):
        self._draw_title("Выбери сложность", 160)
        sub = self.font_small.render("От неё зависит время и множитель очков", True, CLR_TEXT_DIM)
        self.screen.blit(sub, sub.get_rect(center=(SCREEN_W//2, 220)))

        for name, btn in self.btn_diffs.items():
            btn.draw(self.screen)
            cfg = DIFFICULTIES[name]
            info = self.font_small.render(
                f"⏱ {cfg['time']}с   ×{cfg['mult']:.1f}", True, CLR_TEXT_DIM)
            self.screen.blit(info, info.get_rect(center=(btn.rect.centerx, btn.rect.bottom + 18)))

        self.btn_back.draw(self.screen)

    def _draw_playing(self):
        if not self.board:
            return
        
        self.board.draw(self.screen)
        self._draw_hud()
        self.btn_snd.draw(self.screen)
        self.btn_music.draw(self.screen)
        self.btn_menu.draw(self.screen)

        # Метки кнопок
        snd_lbl = "ВКЛ" if self.sound.enabled else "ВЫКЛ"
        mus_lbl = "ВКЛ" if self.sound.music_enabled else "ВЫКЛ"
        sl = self.font_small.render(snd_lbl, True,
                                     (100,220,100) if self.sound.enabled else (220,100,100))
        ml = self.font_small.render(mus_lbl, True,
                                     (100,220,100) if self.sound.music_enabled else (220,100,100))
        rx = BOARD_OFF_X + COLS * CELL_SIZE + 30
        self.screen.blit(sl, (rx + 164, 312))
        self.screen.blit(ml, (rx + 164, 372))

    def _draw_hud(self):
        """HUD: очки, таймер, сложность."""
        # Правая панель
        rx = BOARD_OFF_X + COLS * CELL_SIZE + 30
        panel = pygame.Rect(rx - 10, 20, SCREEN_W - rx + 10 - 10, 260)
        pygame.draw.rect(self.screen, CLR_PANEL, panel, border_radius=12)
        pygame.draw.rect(self.screen, CLR_BORDER, panel, 1, border_radius=12)

        # Очки
        lbl = self.font_small.render("ОЧКИ", True, CLR_TEXT_DIM)
        self.screen.blit(lbl, (rx, 35))
        sc_txt = self.font_large.render(f"{self.score:,}", True, CLR_ACCENT2)
        self.screen.blit(sc_txt, (rx, 58))

        # Таймер
        lbl2 = self.font_small.render("ВРЕМЯ", True, CLR_TEXT_DIM)
        self.screen.blit(lbl2, (rx, 110))
        t = int(math.ceil(self.time_left))
        t_color = (220, 80, 80) if t <= 10 else CLR_TEXT
        t_txt = self.font_large.render(f"{t}с", True, t_color)
        self.screen.blit(t_txt, (rx, 132))

        # Полоска таймера
        cfg = DIFFICULTIES[self.difficulty]
        ratio = max(0, self.time_left / cfg["time"])
        bar_w = 140
        bar_h = 10
        bx, by = rx, 172
        pygame.draw.rect(self.screen, CLR_BORDER, (bx, by, bar_w, bar_h), border_radius=5)
        clr = (int(220 * (1 - ratio) + 60 * ratio),
               int(80 * (1 - ratio) + 200 * ratio),
               80)
        pygame.draw.rect(self.screen, clr,
                         (bx, by, int(bar_w * ratio), bar_h), border_radius=5)

        # Сложность
        d_txt = self.font_small.render(self.difficulty, True, CLR_TEXT_DIM)
        self.screen.blit(d_txt, (rx, 192))

        # Combo
        if self.board and self.board.combo > 1:
            c_txt = self.font_medium.render(f"КОМБО ×{self.board.combo}!", True, CLR_ACCENT2)
            cx = BOARD_OFF_X + COLS * CELL_SIZE // 2
            cy = BOARD_OFF_Y + ROWS * CELL_SIZE + 24
            self.screen.blit(c_txt, c_txt.get_rect(center=(cx, cy)))

    def _draw_gameover(self):
        # Полупрозрачный оверлей
        overlay = pygame.Surface((SCREEN_W, SCREEN_H), pygame.SRCALPHA)
        overlay.fill((0, 0, 0, 160))
        self.screen.blit(overlay, (0, 0))

        cx = SCREEN_W // 2
        self._draw_title("⏰ Время вышло!", 160, color=(220, 80, 80))

        sc_txt = self.font_large.render(f"Ваш счёт: {self.score:,}", True, CLR_ACCENT2)
        self.screen.blit(sc_txt, sc_txt.get_rect(center=(cx, 270)))

        d_txt = self.font_medium.render(f"Сложность: {self.difficulty}", True, CLR_TEXT_DIM)
        self.screen.blit(d_txt, d_txt.get_rect(center=(cx, 320)))

        # Лучший результат
        best = self.high_scores[0]["score"] if self.high_scores else 0
        b_txt = self.font_medium.render(f"Лучший: {best:,}", True, CLR_TEXT)
        self.screen.blit(b_txt, b_txt.get_rect(center=(cx, 370)))

        self.btn_again.draw(self.screen)
        self.btn_gmenu.draw(self.screen)

    def _draw_scores(self):
        self._draw_title("🏆 Таблица рекордов", 100)

        cx = SCREEN_W // 2

        if not self.high_scores:
            t = self.font_medium.render("Пока нет рекордов. Играй!", True, CLR_TEXT_DIM)
            self.screen.blit(t, t.get_rect(center=(cx, 300)))
        else:
            for i, entry in enumerate(self.high_scores[:8]):
                y = 180 + i * 44
                rank_color = [CLR_ACCENT2, (200,200,200), (180,130,60)][min(i, 2)]
                rank = self.font_medium.render(f"#{i+1}", True, rank_color)
                scr  = self.font_medium.render(f"{entry['score']:,}", True, CLR_TEXT)
                diff = self.font_small.render(entry.get('difficulty', '—'), True, CLR_TEXT_DIM)
                self.screen.blit(rank, (cx - 200, y))
                self.screen.blit(scr,  (cx - 80,  y))
                self.screen.blit(diff, (cx + 100,  y + 4))

        self.btn_scores_back.draw(self.screen)

    # ── рекорды ───────────────────────────────────────────────────────────────

    def _load_scores(self) -> list:
        try:
            if os.path.exists(SCORES_FILE):
                with open(SCORES_FILE, "r", encoding="utf-8") as f:
                    return json.load(f)
                
        except Exception:
            pass
        return []
    
    # ── сохраняет результаты в виде JSON ────────────────
    def _save_scores(self):
        try:
            with open(SCORES_FILE, "w", encoding="utf-8") as f:
                json.dump(self.high_scores, f, ensure_ascii=False, indent=2)
        except Exception:
            pass

# 8. ТОЧКА ВХОДА
def main():
    """Запуск игры."""
    # Пробуем импортировать numpy (нужен для звука)
    try:
        import numpy
    except ImportError:
        print("[Gem Blitz] numpy не найден — звук будет отключён.")
        print("Пожалуйста, установите библиотеку 'numpy': pip install numpy")

    game = Game()
    game.run()


if __name__ == "__main__":
    main()
