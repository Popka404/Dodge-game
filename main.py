"""
Игра "Уворачивайся" (Dodge the Blocks)
Простая аркада на Kivy: игрок управляет квадратиком внизу экрана,
двигая его пальцем влево/вправо, и уворачивается от падающих блоков.
За каждый пропущенный блок начисляется очко.
Игра заканчивается, если блок столкнулся с игроком.
"""

import random
from kivy.app import App
from kivy.uix.widget import Widget
from kivy.uix.label import Label
from kivy.uix.button import Button
from kivy.uix.floatlayout import FloatLayout
from kivy.graphics import Color, Rectangle
from kivy.clock import Clock
from kivy.core.window import Window


class Player(Widget):
    def __init__(self, **kwargs):
        super().__init__(**kwargs)
        self.size = (80, 80)
        with self.canvas:
            Color(0.2, 0.8, 0.3, 1)  # зелёный
            self.rect = Rectangle(pos=self.pos, size=self.size)

    def update_graphics(self):
        self.rect.pos = self.pos
        self.rect.size = self.size


class Block(Widget):
    def __init__(self, x, speed, **kwargs):
        super().__init__(**kwargs)
        self.size = (60, 60)
        self.pos = (x, Window.height)
        self.speed = speed
        with self.canvas:
            Color(0.9, 0.2, 0.2, 1)  # красный
            self.rect = Rectangle(pos=self.pos, size=self.size)

    def move(self, dt):
        self.y -= self.speed * dt
        self.rect.pos = self.pos

    def collides_with(self, player):
        return self.collide_widget(player)


class GameWidget(FloatLayout):
    def __init__(self, **kwargs):
        super().__init__(**kwargs)
        self.player = Player(pos=(Window.width / 2 - 40, 20))
        self.add_widget(self.player)

        self.blocks = []
        self.score = 0
        self.game_over = False

        self.score_label = Label(
            text="Очки: 0",
            font_size=28,
            pos_hint={"x": 0, "top": 1},
            size_hint=(None, None),
            size=(200, 50),
        )
        self.add_widget(self.score_label)

        # Управление касанием: палец = целевая позиция игрока по X
        self.touch_x = None

        Clock.schedule_interval(self.spawn_block, 1.2)
        Clock.schedule_interval(self.update, 1 / 60)

    def on_touch_down(self, touch):
        self.touch_x = touch.x
        return super().on_touch_down(touch)

    def on_touch_move(self, touch):
        self.touch_x = touch.x
        return super().on_touch_move(touch)

    def spawn_block(self, dt):
        if self.game_over:
            return
        x = random.randint(0, int(Window.width - 60))
        speed = random.randint(200, 350)
        block = Block(x, speed)
        self.blocks.append(block)
        self.add_widget(block)

    def update(self, dt):
        if self.game_over:
            return

        # Плавное движение игрока к точке касания
        if self.touch_x is not None:
            target = self.touch_x - self.player.width / 2
            self.player.x += (target - self.player.x) * 0.2
            self.player.x = max(0, min(Window.width - self.player.width, self.player.x))
            self.player.update_graphics()

        for block in self.blocks[:]:
            block.move(dt)

            if block.top < 0:
                self.blocks.remove(block)
                self.remove_widget(block)
                self.score += 1
                self.score_label.text = f"Очки: {self.score}"
                continue

            if block.collides_with(self.player):
                self.end_game()
                return

    def end_game(self):
        self.game_over = True
        Clock.unschedule(self.spawn_block)

        over_label = Label(
            text=f"Игра окончена!\nОчки: {self.score}",
            font_size=36,
            pos_hint={"center_x": 0.5, "center_y": 0.6},
            halign="center",
        )
        self.add_widget(over_label)

        restart_btn = Button(
            text="Заново",
            size_hint=(0.4, 0.1),
            pos_hint={"center_x": 0.5, "center_y": 0.4},
        )
        restart_btn.bind(on_release=self.restart)
        self.add_widget(restart_btn)

    def restart(self, instance):
        self.clear_widgets()
        self.__init__()


class DodgeApp(App):
    def build(self):
        Window.clearcolor = (0.05, 0.05, 0.08, 1)
        return GameWidget()


if __name__ == "__main__":
    DodgeApp().run()
