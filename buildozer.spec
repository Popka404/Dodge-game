[app]
title = Dodge Game
android.accept_sdk_license = True
package.name = dodgegame
package.domain = org.myapp

source.dir = .
source.include_exts = py,png,jpg,kv,atlas

version = 1.0

requirements = python3==3.10,kivy==2.2.1

orientation = portrait
fullscreen = 1

# Разрешения (пока не нужны, оставляем пустым)
android.permissions =

# Минимальная и целевая версия Android API
android.minapi = 21
android.api = 33
android.ndk = 25b

[buildozer]
log_level = 2
warn_on_root = 1
