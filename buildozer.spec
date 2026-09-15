[app]
title = Игра в догонялки
android.accept_sdk_license = True
package.name = dodgegame
package.domain = org.myapp
icon.filename = %(source.dir)s/icon.png

source.dir = .
source.include_exts = py,png,jpg,kv,atlas,wav

version = 1.0

requirements = python3,kivy,plyer

orientation = portrait
fullscreen = 1

# Разрешение на вибрацию (для эффекта при столкновении/бонусе)
android.permissions = VIBRATE

# Минимальная и целевая версия Android
android.minapi = 21
android.api = 33
android.ndk = 25b

# Фиксируем стабильную версию сборщика python-for-android,
# чтобы не ловить баги свежих экспериментальных версий
p4a.branch = v2024.01.21

[buildozer]
log_level = 2
warn_on_root = 1
