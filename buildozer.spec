[app]

title = ТехПрофи

package.name = testov
package.domain = ru.testov

version = 0.2.0

source.dir = .

source.include_exts = py,kv,png,jpg,jpeg,json,dat,ttf

icon.filename = %(source.dir)s/assets/icon.png

requirements = python3,kivy

orientation = portrait

fullscreen = 0


# ============================================================
# ANDROID
# ============================================================

android.api = 35

# Python 3.14 / current python-for-android
# requires Android API 24+ for preadv/pwritev
android.minapi = 24

android.archs = arm64-v8a

android.allow_backup = True


# ============================================================
# LOGGING
# ============================================================

log_level = 2


[buildozer]

log_level = 2

warn_on_root = 1
