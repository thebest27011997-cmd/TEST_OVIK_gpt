[app]

title = ТехПрофи

package.name = testov
package.domain = ru.testov

source.dir = .
source.include_exts = py,kv,png,json,ttf

version = 0.2.0

requirements = python3,kivy

orientation = portrait

icon.filename = %(source.dir)s/assets/icon.png

android.api = 35
android.minapi = 23

fullscreen = 0


[buildozer]

log_level = 2
warn_on_root = 1
