"""
Игра "Уворачивайся" v2.0
Аркада на Kivy с прогрессией сложности, разными типами падающих
объектов, звуком/вибрацией, таблицей рекордов и магазином скинов/бонусов.

Структура файла:
1. Сохранение прогресса (монеты, рекорды, скины, апгрейды) — в JSON
2. Данные магазина (скины и апгрейды)
3. Класс Player — сам игрок
4. Класс FallingObject — любой падающий объект (опасность/бонус/монета/бонус-эффект)
5. GameScreen — экран игры со всей логикой
6. MenuScreen — главное меню
7. ShopScreen — магазин
8. App — точка входа
"""

import os
import json
import random
import math

from kivy.app import App
from kivy.uix.widget import Widget
from kivy.uix.label import Label
from kivy.uix.button import Button
from kivy.uix.boxlayout import BoxLayout
from kivy.uix.floatlayout import FloatLayout
from kivy.uix.scrollview import ScrollView
from kivy.uix.gridlayout import GridLayout
from kivy.uix.screenmanager import ScreenManager, Screen, FadeTransition
from kivy.graphics import Color, Rectangle, Ellipse
from kivy.clock import Clock
from kivy.core.window import Window
from kivy.core.audio import SoundLoader

try:
    from plyer import vibrator
except Exception:
    vibrator = None


# ======================================================================
# 1. СОХРАНЕНИЕ ПРОГРЕССА
# ======================================================================

DEFAULT_SAVE = {
    "coins": 0,
    "high_scores": [],          # список лучших результатов (top 5)
    "owned_skins": ["green"],   # какие скины куплены
    "selected_skin": "green",   # какой скин выбран сейчас
    "owned_upgrades": [],       # какие апгрейды куплены
}


def get_save_path():
    app = App.get_running_app()
    directory = app.user_data_dir if app else "."
    if not os.path.exists(directory):
        os.makedirs(directory, exist_ok=True)
    return os.path.join(directory, "save.json")


def load_save():
    path = get_save_path()
    if os.path.exists(path):
        try:
            with open(path, "r", encoding="utf-8") as f:
                data = json.load(f)
            merged = DEFAULT_SAVE.copy()
            merged.update(data)
            return merged
        except Exception:
            pass
    return DEFAULT_SAVE.copy()


def write_save(data):
    path = get_save_path()
    try:
        with open(path, "w", encoding="utf-8") as f:
            json.dump(data, f, ensure_ascii=False, indent=2)
    except Exception:
        pass


# ======================================================================
# 2. ДАННЫЕ МАГАЗИНА
# ======================================================================

SKINS = [
    {"id": "green",  "name": "Зелёный",     "color": (0.20, 0.80, 0.30, 1), "price": 0},
    {"id": "blue",   "name": "Синий",       "color": (0.20, 0.50, 0.90, 1), "price": 30},
    {"id": "purple", "name": "Фиолетовый",  "color": (0.60, 0.30, 0.90, 1), "price": 60},
    {"id": "fire",   "name": "Огненный",    "color": (0.90, 0.30, 0.10, 1), "price": 90},
    {"id": "gold",   "name": "Золотой",     "color": (0.95, 0.80, 0.20, 1), "price": 120},
]

UPGRADES = [
    {
        "id": "slow_start",
        "name": "Мягкий старт",
        "desc": "Первые 3 сек каждой игры блоки падают медленнее",
        "price": 50,
    },
    {
        "id": "long_shield",
        "name": "Долгий щит",
        "desc": "Бонус-щит держится 6 сек вместо 3",
        "price": 80,
    },
    {
        "id": "magnet",
        "name": "Магнит монет",
        "desc": "Монеты сами притягиваются к игроку рядом",
        "price": 100,
    },
]

# Фоновые цвета — экран темнеет/меняет оттенок с ростом счёта
BG_LEVELS = [
    (0.05, 0.05, 0.08, 1),
    (0.05, 0.08, 0.12, 1),
    (0.10, 0.06, 0.14, 1),
    (0.14, 0.06, 0.10, 1),
    (0.12, 0.10, 0.02, 1),
    (0.02, 0.10, 0.10, 1),
]


def get_skin_color(skin_id):
    for s in SKINS:
        if s["id"] == skin_id:
            return s["color"]
    return SKINS[0]["color"]


# Звуки грузим один раз и переиспользуем
_SOUNDS = {}


def play_sound(name):
    snd = _SOUNDS.get(name)
    if snd is None:
        path = os.path.join(os.path.dirname(__file__), f"{name}.wav")
        if os.path.exists(path):
            snd = SoundLoader.load(path)
            _SOUNDS[name] = snd
    if snd:
        snd.stop()
        snd.play()


def vibrate(seconds):
    if vibrator:
        try:
            vibrator.vibrate(seconds)
        except Exception:
            pass


# ======================================================================
# 3. ИГРОК
# ======================================================================

class Player(Widget):
    def __init__(self, color, **kwargs):
        super().__init__(**kwargs)
        # Без этого FloatLayout растягивает виджет на весь экран по умолчанию
        self.size_hint = (None, None)
        self.size = (80, 80)
        with self.canvas:
            self.color_instr = Color(*color)
            self.rect = Rectangle(pos=self.pos, size=self.size)
            # Кольцо щита (видно только когда активен щит)
            self.shield_color = Color(0.3, 0.8, 1, 0)
            self.shield_ring = Ellipse(pos=self.pos, size=self.size)

    def set_color(self, color):
        self.color_instr.rgba = color

    def set_shield_visible(self, visible):
        self.shield_color.a = 0.35 if visible else 0

    def update_graphics(self):
        self.rect.pos = self.pos
        self.rect.size = self.size
        pad = -8
        self.shield_ring.pos = (self.x + pad, self.y + pad)
        self.shield_ring.size = (self.width - pad * 2, self.height - pad * 2)


# ======================================================================
# 4. ПАДАЮЩИЕ ОБЪЕКТЫ
# ======================================================================

# kind: "danger" (опасность), "gold" (бонус-очки), "coin" (валюта),
#       "shield" (бонус: неуязвимость), "slow" (бонус: замедление времени)
KIND_STYLE = {
    "danger": {"color": (0.9, 0.2, 0.2, 1), "shape": "rect", "size": (60, 60)},
    "gold":   {"color": (0.95, 0.85, 0.2, 1), "shape": "rect", "size": (55, 55)},
    "coin":   {"color": (1.0, 0.6, 0.1, 1), "shape": "circle", "size": (34, 34)},
    "shield": {"color": (0.3, 0.75, 1.0, 1), "shape": "circle", "size": (46, 46)},
    "slow":   {"color": (0.65, 0.35, 0.95, 1), "shape": "circle", "size": (46, 46)},
}


class FallingObject(Widget):
    def __init__(self, kind, x, y, speed, **kwargs):
        super().__init__(**kwargs)
        style = KIND_STYLE[kind]
        self.kind = kind
        # Без этого FloatLayout растягивает виджет на весь экран по умолчанию
        self.size_hint = (None, None)
        self.size = style["size"]
        self.pos = (x, y)
        self.speed = speed
        with self.canvas:
            Color(*style["color"])
            if style["shape"] == "circle":
                self.shape = Ellipse(pos=self.pos, size=self.size)
            else:
                self.shape = Rectangle(pos=self.pos, size=self.size)

    def move(self, dt, speed_multiplier):
        self.y -= self.speed * speed_multiplier * dt
        self.shape.pos = self.pos

    def nudge_toward(self, target_x, target_y, dt, strength=260):
        dx = target_x - self.center_x
        dy = target_y - self.center_y
        dist = max(1, math.hypot(dx, dy))
        self.x += dx / dist * strength * dt
        self.y += dy / dist * strength * dt
        self.shape.pos = self.pos

    def collides_with(self, player):
        return self.collide_widget(player)


# Веса выпадения типов объектов (чем больше — тем чаще)
SPAWN_WEIGHTS = [
    ("danger", 60),
    ("coin", 22),
    ("gold", 10),
    ("shield", 4),
    ("slow", 4),
]


def pick_kind():
    total = sum(w for _, w in SPAWN_WEIGHTS)
    r = random.uniform(0, total)
    upto = 0
    for kind, w in SPAWN_WEIGHTS:
        upto += w
        if r <= upto:
            return kind
    return "danger"


# ======================================================================
# 5. ЭКРАН ИГРЫ
# ======================================================================

class GameScreen(Screen):
    def __init__(self, **kwargs):
        super().__init__(**kwargs)
        self.save = load_save()
        self.started = False
        self._build_ui()
        # Откладываем старт на один кадр — к этому моменту self.width/height
        # уже точно равны реальному размеру экрана (защита от бага с
        # "мгновенным проигрышем" на некоторых Android-устройствах).
        Clock.schedule_once(self._start_game, 0)

    def _build_ui(self):
        self.root_layout = FloatLayout()
        self.add_widget(self.root_layout)

        self.score_label = Label(
            text="Очки: 0", font_size=26,
            pos_hint={"x": 0.02, "top": 0.99}, size_hint=(0.4, 0.08),
            halign="left", valign="middle",
        )
        self.coins_label = Label(
            text="Монеты: 0", font_size=22,
            pos_hint={"right": 0.98, "top": 0.99}, size_hint=(0.4, 0.08),
            halign="right", valign="middle",
        )
        self.root_layout.add_widget(self.score_label)
        self.root_layout.add_widget(self.coins_label)

    def _start_game(self, dt):
        width = self.width or Window.width

        skin_color = get_skin_color(self.save.get("selected_skin", "green"))
        self.player = Player(skin_color, pos=(width / 2 - 40, 20))
        self.root_layout.add_widget(self.player)

        self.objects = []
        self.score = 0
        self.run_coins = 0
        self.game_over = False
        self.elapsed = 0.0
        self.spawn_accumulator = 0.0
        self.spawn_interval = 1.2

        self.shield_timer = 0.0
        self.slow_timer = 0.0
        # Небольшая неуязвимость в начале, чтобы не было ложных столкновений
        self.invulnerable_timer = 1.5
        if "slow_start" in self.save.get("owned_upgrades", []):
            self.invulnerable_timer = 1.5  # уже учтено ниже мягким стартом скорости

        self.touch_x = None
        self.started = True

        self._bg_color_instr = None
        self._current_bg_index = -1

        Clock.schedule_interval(self.update, 1 / 60)

    def on_touch_down(self, touch):
        if self.started and not self.game_over:
            self.touch_x = touch.x
        return super().on_touch_down(touch)

    def on_touch_move(self, touch):
        if self.started and not self.game_over:
            self.touch_x = touch.x
        return super().on_touch_move(touch)

    # ------------------------------------------------------------
    def spawn_object(self):
        width = self.width or Window.width
        height = self.height or Window.height
        kind = pick_kind()
        style = KIND_STYLE[kind]
        x = random.randint(0, max(0, int(width - style["size"][0])))

        base_min, base_max = 200, 320
        speed = random.randint(base_min, base_max)
        obj = FallingObject(kind, x, height, speed)
        self.objects.append(obj)
        self.root_layout.add_widget(obj)

    def _update_background(self):
        index = min(self.score // 15, len(BG_LEVELS) - 1)
        if index != self._current_bg_index:
            self._current_bg_index = index
            Window.clearcolor = BG_LEVELS[index]

    def update(self, dt):
        if self.game_over or not self.started:
            return

        self.elapsed += dt
        if self.invulnerable_timer > 0:
            self.invulnerable_timer -= dt
        if self.shield_timer > 0:
            self.shield_timer -= dt
        if self.slow_timer > 0:
            self.slow_timer -= dt
        self.player.set_shield_visible(self.shield_timer > 0)
        self.player.update_graphics()

        # --- Сложность растёт со временем ---
        difficulty = min(self.elapsed / 40.0, 2.2)  # максимум в ~1.5 мин
        speed_multiplier = 1.0 + difficulty
        if self.slow_timer > 0:
            speed_multiplier *= 0.45
        if "slow_start" in self.save.get("owned_upgrades", []) and self.elapsed < 3:
            speed_multiplier *= 0.6

        self.spawn_interval = max(0.45, 1.2 - difficulty * 0.3)
        self.spawn_accumulator += dt
        if self.spawn_accumulator >= self.spawn_interval:
            self.spawn_accumulator = 0
            self.spawn_object()

        width = self.width or Window.width

        # --- Движение игрока к точке касания ---
        if self.touch_x is not None:
            target = self.touch_x - self.player.width / 2
            self.player.x += (target - self.player.x) * 0.25
            self.player.x = max(0, min(width - self.player.width, self.player.x))
            self.player.update_graphics()

        has_magnet = "magnet" in self.save.get("owned_upgrades", [])

        for obj in self.objects[:]:
            if has_magnet and obj.kind == "coin":
                dist = math.hypot(
                    obj.center_x - self.player.center_x,
                    obj.center_y - self.player.center_y,
                )
                if dist < 220:
                    obj.nudge_toward(self.player.center_x, self.player.center_y, dt)

            obj.move(dt, speed_multiplier)

            if obj.top < 0:
                self.objects.remove(obj)
                self.root_layout.remove_widget(obj)
                continue

            if obj.collides_with(self.player):
                self._handle_pickup(obj)

        self._update_background()

    def _handle_pickup(self, obj):
        self.objects.remove(obj)
        self.root_layout.remove_widget(obj)

        if obj.kind == "danger":
            if self.shield_timer > 0 or self.invulnerable_timer > 0:
                return  # щит поглотил удар
            self.end_game()
            return

        if obj.kind == "coin":
            self.run_coins += 1
            self.coins_label.text = f"Монеты: {self.run_coins}"
            play_sound("coin")

        elif obj.kind == "gold":
            self.score += 5
            self.score_label.text = f"Очки: {self.score}"
            play_sound("gold")

        elif obj.kind == "shield":
            duration = 6 if "long_shield" in self.save.get("owned_upgrades", []) else 3
            self.shield_timer = duration
            play_sound("powerup")
            vibrate(0.05)

        elif obj.kind == "slow":
            self.slow_timer = 4
            play_sound("powerup")

    # ------------------------------------------------------------
    def end_game(self):
        self.game_over = True
        Clock.unschedule(self.update)
        play_sound("hit")
        vibrate(0.15)

        # Сохраняем результат
        self.save["coins"] = self.save.get("coins", 0) + self.run_coins
        scores = self.save.get("high_scores", [])
        scores.append(self.score)
        scores = sorted(scores, reverse=True)[:5]
        self.save["high_scores"] = scores
        write_save(self.save)

        best = scores[0] if scores else self.score
        is_record = self.score > 0 and self.score == best

        overlay = BoxLayout(orientation="vertical", spacing=14,
                             pos_hint={"center_x": 0.5, "center_y": 0.5},
                             size_hint=(0.8, 0.5))
        title = "Новый рекорд!" if is_record else "Игра окончена!"
        overlay.add_widget(Label(text=title, font_size=32))
        overlay.add_widget(Label(
            text=f"Очки: {self.score}\nСобрано монет: {self.run_coins}",
            font_size=22, halign="center",
        ))

        btn_row = BoxLayout(spacing=10, size_hint=(1, 0.4))
        retry_btn = Button(text="Заново")
        retry_btn.bind(on_release=lambda *_: self.manager.app_restart_game())
        menu_btn = Button(text="В меню")
        menu_btn.bind(on_release=lambda *_: self.manager.app_go_menu())
        btn_row.add_widget(retry_btn)
        btn_row.add_widget(menu_btn)
        overlay.add_widget(btn_row)

        self.root_layout.add_widget(overlay)

    def stop_game(self):
        """Останавливает все таймеры экрана — вызывается перед его удалением."""
        Clock.unschedule(self.update)


# ======================================================================
# 6. ГЛАВНОЕ МЕНЮ
# ======================================================================

class MenuScreen(Screen):
    def __init__(self, **kwargs):
        super().__init__(**kwargs)
        Window.clearcolor = (0.05, 0.05, 0.08, 1)
        self.layout = BoxLayout(orientation="vertical", spacing=16, padding=40)
        self.add_widget(self.layout)

        self.layout.add_widget(Label(text="Уворачивайся", font_size=44, size_hint=(1, 0.25)))

        self.info_label = Label(text="", font_size=20, size_hint=(1, 0.25))
        self.layout.add_widget(self.info_label)

        play_btn = Button(text="Играть", font_size=26, size_hint=(1, 0.18))
        play_btn.bind(on_release=lambda *_: self.manager.app_go_game())
        self.layout.add_widget(play_btn)

        shop_btn = Button(text="Магазин", font_size=22, size_hint=(1, 0.15))
        shop_btn.bind(on_release=lambda *_: self.manager.app_go_shop())
        self.layout.add_widget(shop_btn)

        legend = Label(
            text=(
                "[color=ff4d4d]Красный[/color] — опасность   "
                "[color=ffd633]Жёлтый[/color] — бонус +очки\n"
                "[color=ff9933]Оранжевый круг[/color] — монета   "
                "[color=4dc3ff]Голубой[/color] — щит   "
                "[color=a64dff]Фиолетовый[/color] — замедление"
            ),
            markup=True, font_size=14, size_hint=(1, 0.17),
        )
        self.layout.add_widget(legend)

    def on_pre_enter(self):
        save = load_save()
        best = max(save.get("high_scores", [0]) or [0])
        top = save.get("high_scores", [])
        top_text = ", ".join(str(s) for s in top) if top else "пока нет результатов"
        self.info_label.text = (
            f"Монеты: {save.get('coins', 0)}\n"
            f"Рекорд: {best}\n"
            f"Топ-5: {top_text}"
        )


# ======================================================================
# 7. МАГАЗИН
# ======================================================================

class ShopScreen(Screen):
    def __init__(self, **kwargs):
        super().__init__(**kwargs)
        root = BoxLayout(orientation="vertical", padding=20, spacing=10)
        self.add_widget(root)

        self.coins_label = Label(text="Монеты: 0", font_size=24, size_hint=(1, 0.1))
        root.add_widget(self.coins_label)

        scroll = ScrollView(size_hint=(1, 0.75))
        self.grid = GridLayout(cols=1, spacing=12, size_hint_y=None, padding=(0, 10))
        self.grid.bind(minimum_height=self.grid.setter("height"))
        scroll.add_widget(self.grid)
        root.add_widget(scroll)

        back_btn = Button(text="Назад в меню", size_hint=(1, 0.12))
        back_btn.bind(on_release=lambda *_: self.manager.app_go_menu())
        root.add_widget(back_btn)

    def on_pre_enter(self):
        self.save = load_save()
        self.coins_label.text = f"Монеты: {self.save.get('coins', 0)}"
        self.grid.clear_widgets()

        self.grid.add_widget(Label(text="— Скины —", font_size=22, size_hint_y=None, height=40))
        for skin in SKINS:
            self.grid.add_widget(self._build_skin_row(skin))

        self.grid.add_widget(Label(text="— Апгрейды —", font_size=22, size_hint_y=None, height=40))
        for up in UPGRADES:
            self.grid.add_widget(self._build_upgrade_row(up))

    def _build_skin_row(self, skin):
        row = BoxLayout(size_hint_y=None, height=70, spacing=10)

        swatch = Widget(size_hint=(0.15, 1))
        with swatch.canvas:
            Color(*skin["color"])
            rect = Rectangle(pos=swatch.pos, size=(50, 50))

        def sync_rect(instance, _):
            rect.pos = (instance.x, instance.center_y - 25)
        swatch.bind(pos=sync_rect, size=sync_rect)

        row.add_widget(swatch)
        row.add_widget(Label(text=skin["name"], font_size=18))

        owned = skin["id"] in self.save.get("owned_skins", [])
        selected = skin["id"] == self.save.get("selected_skin")

        if selected:
            btn = Button(text="Выбрано", disabled=True)
        elif owned:
            btn = Button(text="Выбрать")
            btn.bind(on_release=lambda *_: self._select_skin(skin["id"]))
        else:
            btn = Button(text=f"Купить {skin['price']}")
            btn.bind(on_release=lambda *_: self._buy_skin(skin))

        row.add_widget(btn)
        return row

    def _build_upgrade_row(self, up):
        row = BoxLayout(size_hint_y=None, height=70, spacing=10)
        text = f"{up['name']}\n[size=13]{up['desc']}[/size]"
        row.add_widget(Label(text=text, markup=True, font_size=17, halign="left"))

        owned = up["id"] in self.save.get("owned_upgrades", [])
        if owned:
            btn = Button(text="Куплено", disabled=True)
        else:
            btn = Button(text=f"Купить {up['price']}")
            btn.bind(on_release=lambda *_: self._buy_upgrade(up))
        row.add_widget(btn)
        return row

    def _buy_skin(self, skin):
        if self.save.get("coins", 0) >= skin["price"]:
            self.save["coins"] -= skin["price"]
            self.save.setdefault("owned_skins", []).append(skin["id"])
            self.save["selected_skin"] = skin["id"]
            write_save(self.save)
            self.on_pre_enter()

    def _select_skin(self, skin_id):
        self.save["selected_skin"] = skin_id
        write_save(self.save)
        self.on_pre_enter()

    def _buy_upgrade(self, up):
        if self.save.get("coins", 0) >= up["price"]:
            self.save["coins"] -= up["price"]
            self.save.setdefault("owned_upgrades", []).append(up["id"])
            write_save(self.save)
            self.on_pre_enter()


# ======================================================================
# 8. ПРИЛОЖЕНИЕ
# ======================================================================

class DodgeScreenManager(ScreenManager):
    def app_go_menu(self):
        self._cleanup_game()
        self.transition = FadeTransition(duration=0.2)
        self.current = "menu"

    def app_go_shop(self):
        self.transition = FadeTransition(duration=0.2)
        self.current = "shop"

    def app_go_game(self):
        self._cleanup_game()
        self.add_widget(GameScreen(name="game"))
        self.transition = FadeTransition(duration=0.2)
        self.current = "game"

    def app_restart_game(self):
        self.app_go_game()

    def _cleanup_game(self):
        old = self.get_screen("game") if self.has_screen("game") else None
        if old:
            old.stop_game()
            self.remove_widget(old)


class DodgeApp(App):
    def build(self):
        sm = DodgeScreenManager()
        sm.add_widget(MenuScreen(name="menu"))
        sm.add_widget(ShopScreen(name="shop"))
        sm.current = "menu"
        return sm


if __name__ == "__main__":
    DodgeApp().run()
