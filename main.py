 Button(text=f"Купить {skin['price']}")
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
