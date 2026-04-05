[app]

# ── Identity ──────────────────────────────────────────────────────────────
title           = Chameleon Wallpaper
package.name    = chameleon
package.domain  = com.chameleon

# ── Source ───────────────────────────────────────────────────────────────
source.dir      = .
source.include_exts = py,png,jpg,kv,atlas,ttf
source.exclude_dirs = tests, bin, venv, .git, __pycache__

# ── Version ───────────────────────────────────────────────────────────────
version         = 1.0

# ── Requirements ──────────────────────────────────────────────────────────
# All Python packages bundled into the APK
requirements = python3,kivy==2.3.0,kivymd,pillow,android,pyjnius

# ── Orientation & UI ──────────────────────────────────────────────────────
orientation     = portrait
fullscreen      = 0

# ── Android SDK/NDK ──────────────────────────────────────────────────────
android.minapi  = 26
android.api     = 34
android.ndk     = 25b
android.sdk     = 34
android.archs   = arm64-v8a, armeabi-v7a

# ── Permissions ───────────────────────────────────────────────────────────
android.permissions = \
    CAMERA, \
    SET_WALLPAPER, \
    SET_WALLPAPER_HINTS, \
    FOREGROUND_SERVICE, \
    FOREGROUND_SERVICE_CAMERA, \
    POST_NOTIFICATIONS, \
    RECEIVE_BOOT_COMPLETED

# ── Extras ────────────────────────────────────────────────────────────────
android.add_activities                  =
android.allow_backup                    = True
android.manifest.intent_filters         =

# Foreground service type for camera (Android 14+)
android.add_manifest_application_arguments = android:requestLegacyExternalStorage="true"

# Keep screen on
android.wakelock                        = False

# ── Build ─────────────────────────────────────────────────────────────────
[buildozer]
log_level   = 2
warn_on_root = 1
