"""
Chameleon Wallpaper — Python/Kivy Android App
=============================================
Reads live camera frames, extracts dominant color,
and sets device wallpaper in real-time.
"""

import threading
import time
from colorsys import rgb_to_hls, hls_to_rgb

from kivy.app import App
from kivy.clock import Clock, mainthread
from kivy.core.window import Window
from kivy.graphics import Color, RoundedRectangle, Ellipse
from kivy.graphics.texture import Texture
from kivy.lang import Builder
from kivy.properties import (
    ListProperty, StringProperty, NumericProperty, BooleanProperty
)
from kivy.uix.camera import Camera
from kivy.uix.widget import Widget
from kivy.utils import platform

# Android-specific imports (only on device)
if platform == "android":
    from android.permissions import request_permissions, Permission
    from jnius import autoclass, cast

    WallpaperManager = autoclass("android.app.WallpaperManager")
    Bitmap = autoclass("android.graphics.Bitmap")
    BitmapConfig = autoclass("android.graphics.Bitmap$Config")
    Canvas = autoclass("android.graphics.Canvas")
    Paint = autoclass("android.graphics.Paint")
    Color_android = autoclass("android.graphics.Color")
    RadialGradient = autoclass("android.graphics.RadialGradient")
    LinearGradient = autoclass("android.graphics.LinearGradient")
    ShaderTileMode = autoclass("android.graphics.Shader$TileMode")
    PythonActivity = autoclass("org.kivy.android.PythonActivity")
    Intent = autoclass("android.content.Intent")
    Service = autoclass("android.app.Service")
    FLAG_SYSTEM = 1
    FLAG_LOCK = 2

# ── KV Layout ──────────────────────────────────────────────────────────────
KV = """
#:import dp kivy.metrics.dp
#:import sp kivy.metrics.sp

<RoundedButton@Button>:
    background_normal: ''
    background_color: 0, 0, 0, 0
    canvas.before:
        Color:
            rgba: self.bg_color if not self.state == 'down' else [c*0.7 for c in self.bg_color]
        RoundedRectangle:
            pos: self.pos
            size: self.size
            radius: [self.radius_val]
    bg_color: (1, 1, 1, 0.12)
    radius_val: dp(14)

<ChameleonRoot>:
    orientation: 'vertical'
    spacing: 0
    padding: 0

    # ── Dynamic background canvas ──
    canvas.before:
        Color:
            rgba: root.bg_color
        Rectangle:
            pos: self.pos
            size: self.size
        # Blob 1 – top left
        Color:
            rgba: root.blob1_color
        Ellipse:
            pos: -self.width * 0.2, self.height * 0.55
            size: self.width * 0.85, self.width * 0.85
        # Blob 2 – bottom right
        Color:
            rgba: root.blob2_color
        Ellipse:
            pos: self.width * 0.35, -self.height * 0.1
            size: self.width * 0.9, self.width * 0.9
        # Blob 3 – center accent
        Color:
            rgba: root.blob3_color
        Ellipse:
            pos: self.width * 0.1, self.height * 0.25
            size: self.width * 0.6, self.width * 0.6

    # Hidden camera (processes frames, not shown)
    Camera:
        id: cam
        resolution: (320, 240)
        play: root.cam_active
        size: (1, 1)
        opacity: 0

    # ── STATUS PILL ──
    BoxLayout:
        size_hint_y: None
        height: dp(48)
        padding: [dp(20), dp(10), dp(20), 0]

        BoxLayout:
            size_hint_x: None
            width: dp(120)
            spacing: dp(6)
            canvas.before:
                Color:
                    rgba: (0, 0, 0, 0.4)
                RoundedRectangle:
                    pos: self.pos
                    size: self.size
                    radius: [dp(20)]
            padding: [dp(10), dp(6)]

            Widget:
                size_hint: None, None
                size: dp(8), dp(8)
                pos_hint: {'center_y': 0.5}
                canvas:
                    Color:
                        rgba: (0.13, 0.77, 0.37, 1) if root.cam_active else (0.94, 0.27, 0.27, 1)
                    Ellipse:
                        pos: self.pos
                        size: self.size

            Label:
                text: "LIVE" if root.cam_active else "OFF"
                font_size: sp(11)
                color: (1, 1, 1, 0.8)
                bold: True

        Widget:

    # ── SWATCH + HEX ──
    BoxLayout:
        orientation: 'vertical'
        size_hint_y: 0.45
        padding: [dp(20), dp(10)]
        spacing: dp(12)

        # Big color circle
        Widget:
            size_hint_y: 0.7
            canvas:
                Color:
                    rgba: root.swatch_color
                Ellipse:
                    pos: (self.width - min(self.width, self.height) * 0.55) / 2 + self.x, \
                         (self.height - min(self.width, self.height) * 0.55) / 2 + self.y
                    size: min(self.width, self.height) * 0.55, min(self.width, self.height) * 0.55
                Color:
                    rgba: (1, 1, 1, 0.15)
                    # ring
                Line:
                    circle: \
                        self.x + self.width / 2, \
                        self.y + self.height / 2, \
                        min(self.width, self.height) * 0.29
                    width: dp(1.5)

        # HEX label
        Label:
            text: root.hex_color
            font_size: sp(30)
            bold: False
            color: (1, 1, 1, 0.95)
            font_name: 'RobotoMono'
            size_hint_y: None
            height: dp(40)

        # Color name
        Label:
            text: root.color_name
            font_size: sp(13)
            color: (1, 1, 1, 0.5)
            size_hint_y: None
            height: dp(20)

    # ── PALETTE ROW ──
    BoxLayout:
        size_hint_y: None
        height: dp(52)
        padding: [dp(20), dp(4)]
        spacing: dp(8)

        Label:
            text: "Recent"
            font_size: sp(11)
            color: (1, 1, 1, 0.35)
            size_hint_x: None
            width: dp(44)

        PaletteStrip:
            id: palette
            size_hint_x: 1

    # ── CONTROL CARD ──
    BoxLayout:
        orientation: 'vertical'
        size_hint_y: None
        height: dp(270)
        padding: [dp(20), dp(16), dp(20), dp(36)]
        spacing: dp(14)
        canvas.before:
            Color:
                rgba: (0.07, 0.07, 0.16, 0.85)
            RoundedRectangle:
                pos: self.pos
                size: self.size
                radius: [dp(28), dp(28), 0, 0]

        # Mode selector
        BoxLayout:
            size_hint_y: None
            height: dp(42)
            spacing: dp(4)
            canvas.before:
                Color:
                    rgba: (1, 1, 1, 0.06)
                RoundedRectangle:
                    pos: self.pos
                    size: self.size
                    radius: [dp(12)]

            RoundedButton:
                text: "Solid"
                font_size: sp(12)
                color: (1,1,1,1) if root.mode == 'solid' else (1,1,1,0.4)
                bg_color: (1,1,1,0.2) if root.mode == 'solid' else (0,0,0,0)
                on_press: root.set_mode('solid')

            RoundedButton:
                text: "Gradient"
                font_size: sp(12)
                color: (1,1,1,1) if root.mode == 'gradient' else (1,1,1,0.4)
                bg_color: (1,1,1,0.2) if root.mode == 'gradient' else (0,0,0,0)
                on_press: root.set_mode('gradient')

            RoundedButton:
                text: "Aurora"
                font_size: sp(12)
                color: (1,1,1,1) if root.mode == 'aurora' else (1,1,1,0.4)
                bg_color: (1,1,1,0.2) if root.mode == 'aurora' else (0,0,0,0)
                on_press: root.set_mode('aurora')

        # Speed row
        BoxLayout:
            size_hint_y: None
            height: dp(36)
            spacing: dp(10)

            Label:
                text: "Speed"
                font_size: sp(11)
                color: (1, 1, 1, 0.4)
                size_hint_x: None
                width: dp(44)

            Slider:
                id: speed_slider
                min: 1
                max: 5
                value: 3
                step: 1
                on_value: root.set_speed(int(self.value))
                cursor_size: (dp(20), dp(20))

            Label:
                id: speed_label
                text: "Normal"
                font_size: sp(11)
                color: (1, 1, 1, 0.7)
                size_hint_x: None
                width: dp(68)
                halign: 'right'

        # Action buttons
        BoxLayout:
            size_hint_y: None
            height: dp(52)
            spacing: dp(10)

            RoundedButton:
                text: "❄  Freeze"
                font_size: sp(13)
                color: (1, 1, 1, 0.85)
                on_press: root.toggle_freeze()

            RoundedButton:
                text: "Stop" if root.cam_active else "Start"
                font_size: sp(15)
                bold: True
                color: (0, 0, 0, 1)
                bg_color: (0.94, 0.27, 0.27, 1) if root.cam_active else (0.13, 0.77, 0.37, 1)
                radius_val: dp(16)
                on_press: root.toggle_camera()

            RoundedButton:
                text: "⇄  Cam"
                font_size: sp(13)
                color: (1, 1, 1, 0.85)
                on_press: root.switch_camera()
"""

# ── Palette Widget ──────────────────────────────────────────────────────────
class PaletteStrip(Widget):
    colors = ListProperty([])

    def on_colors(self, *_):
        self.canvas.clear()
        if not self.colors:
            return
        with self.canvas:
            size = min(self.height, 44)
            gap = 10
            for i, c in enumerate(self.colors[:7]):
                x = self.x + i * (size + gap)
                if x + size > self.right:
                    break
                Color(*c)
                RoundedRectangle(
                    pos=(x, self.y + (self.height - size) / 2),
                    size=(size, size),
                    radius=[14]
                )
                Color(1, 1, 1, 0.15)
                RoundedRectangle(
                    pos=(x, self.y + (self.height - size) / 2),
                    size=(size, size),
                    radius=[14]
                )

    def add_color(self, rgba):
        new = list(self.colors)
        if not new or new[0] != rgba:
            new.insert(0, rgba)
            self.colors = new[:7]


# ── Root Widget ─────────────────────────────────────────────────────────────
class ChameleonRoot(Widget):
    from kivy.uix.boxlayout import BoxLayout
    __bases__ = (BoxLayout,)

    bg_color       = ListProperty([0.05, 0.05, 0.10, 1])
    blob1_color    = ListProperty([0.10, 0.10, 0.30, 0.65])
    blob2_color    = ListProperty([0.15, 0.05, 0.25, 0.55])
    blob3_color    = ListProperty([0.20, 0.20, 0.40, 0.25])
    swatch_color   = ListProperty([0.10, 0.10, 0.30, 1])
    hex_color      = StringProperty("#------")
    color_name     = StringProperty("Point camera at any surface")
    mode           = StringProperty("gradient")
    cam_active     = BooleanProperty(False)
    frozen         = BooleanProperty(False)
    speed_ms       = NumericProperty(1000)
    front_camera   = BooleanProperty(False)

    _last_wall_time = 0
    _palette_colors = []

    SPEED_LABELS = {1: "Instant", 2: "Fast", 3: "Normal", 4: "Slow", 5: "Dreamy"}
    SPEED_MS     = {1: 200,       2: 500,  3: 1000,   4: 2500, 5: 5000}

    def toggle_camera(self):
        if not self.cam_active:
            self._request_permissions()
        else:
            self.cam_active = False

    def _request_permissions(self):
        if platform == "android":
            request_permissions(
                [Permission.CAMERA, Permission.SET_WALLPAPER],
                self._on_permissions
            )
        else:
            self.cam_active = True
            Clock.schedule_interval(self._analyze_frame, 0.3)

    def _on_permissions(self, perms, results):
        if all(results):
            self.cam_active = True
            Clock.schedule_interval(self._analyze_frame, 0.3)

    def _analyze_frame(self, dt):
        if not self.cam_active or self.frozen:
            return
        cam = self.ids.get("cam")
        if not cam or not cam.texture:
            return
        try:
            tex = cam.texture
            buf = tex.pixels  # RGBA bytes
            w, h = tex.size
            r, g, b = self._dominant_color(buf, w, h)
            self._apply_color(r, g, b)
        except Exception as e:
            pass

    def _dominant_color(self, buf, w, h):
        """Average pixels on a 20×15 grid sample for speed."""
        step_x = max(1, w // 20)
        step_y = max(1, h // 15)
        r_sum = g_sum = b_sum = count = 0
        for x in range(0, w, step_x):
            for y in range(0, h, step_y):
                idx = (y * w + x) * 4
                if idx + 2 < len(buf):
                    r_sum += buf[idx]
                    g_sum += buf[idx + 1]
                    b_sum += buf[idx + 2]
                    count += 1
        if count == 0:
            return 30, 30, 80
        return r_sum // count, g_sum // count, b_sum // count

    @mainthread
    def _apply_color(self, r, g, b):
        rf, gf, bf = r / 255.0, g / 255.0, b / 255.0

        # Convert to HLS (Kivy colorsys uses HLS not HSL)
        h, l, s = rgb_to_hls(rf, gf, bf)

        dark_l  = max(0.03, l - 0.18)
        mid_l   = min(0.90, l + 0.05)
        light_l = min(0.90, l + 0.28)

        # UI colors
        self.bg_color     = [*hls_to_rgb(h, dark_l, s), 1.0]
        self.blob1_color  = [*hls_to_rgb(h, mid_l, s), 0.65]
        self.blob2_color  = [*hls_to_rgb((h + 0.08) % 1.0, dark_l, s), 0.55]
        self.blob3_color  = [*hls_to_rgb((h + 0.5) % 1.0, light_l * 0.6, max(0.2, s - 0.2)), 0.25]
        self.swatch_color = [rf, gf, bf, 1.0]
        self.hex_color    = "#{:02X}{:02X}{:02X}".format(r, g, b)
        self.color_name   = self._color_name(h, s, l)

        # Palette
        self.ids.palette.add_color([rf, gf, bf, 1.0])

        # Set wallpaper (rate-limited)
        now = time.time()
        if now - self._last_wall_time >= self.speed_ms / 1000.0:
            self._last_wall_time = now
            threading.Thread(
                target=self._set_wallpaper,
                args=(r, g, b, h, s, l),
                daemon=True
            ).start()

    def _set_wallpaper(self, r, g, b, h, s, l):
        """Render and set the actual device wallpaper (Android only)."""
        if platform != "android":
            return
        try:
            context = PythonActivity.mActivity
            wm = WallpaperManager.getInstance(context)
            dw = wm.getDesiredMinimumWidth()  or 1080
            dh = wm.getDesiredMinimumHeight() or 1920

            bmp = Bitmap.createBitmap(dw, dh, BitmapConfig.ARGB_8888)
            canvas = Canvas(bmp)
            paint = Paint()
            paint.setAntiAlias(True)

            if self.mode == "solid":
                self._render_solid(canvas, paint, dw, dh, r, g, b, h, s, l)
            elif self.mode == "aurora":
                self._render_aurora(canvas, paint, dw, dh, r, g, b, h, s, l)
            else:
                self._render_gradient(canvas, paint, dw, dh, r, g, b, h, s, l)

            wm.setBitmap(bmp, None, True, FLAG_SYSTEM | FLAG_LOCK)
            bmp.recycle()
        except Exception as e:
            pass

    def _hls_to_android_color(self, h, l, s, alpha=255):
        rgb = hls_to_rgb(h, l, s)
        r = int(rgb[0] * 255)
        g = int(rgb[1] * 255)
        b = int(rgb[2] * 255)
        return Color_android.argb(alpha, r, g, b)

    def _render_solid(self, canvas, paint, dw, dh, r, g, b, h, s, l):
        bg_color = self._hls_to_android_color(h, max(0.03, l - 0.15), s)
        canvas.drawColor(bg_color)
        # Vignette
        cx, cy = dw / 2.0, dh / 2.0
        radius = max(dw, dh) * 1.0
        vgradient = RadialGradient(
            cx, cy, radius,
            [Color_android.TRANSPARENT, Color_android.argb(180, 0, 0, 0)],
            [0.4, 1.0], ShaderTileMode.CLAMP
        )
        paint.setShader(vgradient)
        canvas.drawRect(0, 0, dw, dh, paint)
        paint.setShader(None)

    def _render_gradient(self, canvas, paint, dw, dh, r, g, b, h, s, l):
        bg_color = self._hls_to_android_color(h, max(0.03, l - 0.22), min(s, 0.8))
        canvas.drawColor(bg_color)

        blob1_color = self._hls_to_android_color(h, min(0.75, l + 0.2), s, 160)
        grad1 = RadialGradient(
            dw * 0.2, dh * 0.2, dw * 0.8,
            [blob1_color, Color_android.TRANSPARENT],
            [0.0, 1.0], ShaderTileMode.CLAMP
        )
        paint.setShader(grad1)
        canvas.drawRect(0, 0, dw, dh, paint)

        blob2_color = self._hls_to_android_color((h + 0.08) % 1.0, min(0.65, l + 0.1), s, 140)
        grad2 = RadialGradient(
            dw * 0.8, dh * 0.75, dw * 0.7,
            [blob2_color, Color_android.TRANSPARENT],
            [0.0, 1.0], ShaderTileMode.CLAMP
        )
        paint.setShader(grad2)
        canvas.drawRect(0, 0, dw, dh, paint)

        # White glow center
        grad3 = RadialGradient(
            dw * 0.5, dh * 0.35, dw * 0.45,
            [Color_android.argb(60, 255, 255, 255), Color_android.TRANSPARENT],
            [0.0, 1.0], ShaderTileMode.CLAMP
        )
        paint.setShader(grad3)
        canvas.drawRect(0, 0, dw, dh, paint)

        # Vignette
        vgradient = RadialGradient(
            dw / 2.0, dh / 2.0, max(dw, dh) * 1.0,
            [Color_android.TRANSPARENT, Color_android.argb(160, 0, 0, 0)],
            [0.35, 1.0], ShaderTileMode.CLAMP
        )
        paint.setShader(vgradient)
        canvas.drawRect(0, 0, dw, dh, paint)
        paint.setShader(None)

    def _render_aurora(self, canvas, paint, dw, dh, r, g, b, h, s, l):
        bg_color = self._hls_to_android_color(h, max(0.03, l - 0.25), min(s, 0.7))
        canvas.drawColor(bg_color)

        band_hues = [h, (h + 0.11) % 1.0, (h + 0.25) % 1.0, (h + 0.42) % 1.0]
        for i, bh in enumerate(band_hues):
            y_pos = dh * (0.2 + i * 0.18)
            band_h = dh * 0.22
            bc = self._hls_to_android_color(bh, min(0.70, l + 0.25), min(0.95, s + 0.2), 120)
            lgrad = LinearGradient(
                0, y_pos - band_h / 2, 0, y_pos + band_h / 2,
                [Color_android.TRANSPARENT, bc, Color_android.TRANSPARENT],
                [0.0, 0.5, 1.0], ShaderTileMode.CLAMP
            )
            paint.setShader(lgrad)
            canvas.drawRect(0, y_pos - band_h / 2, dw, y_pos + band_h / 2, paint)

        paint.setShader(None)
        paint.setColor(Color_android.argb(180, 255, 255, 255))
        import random
        rng = random.Random(42)
        for _ in range(120):
            sx = rng.random() * dw
            sy = rng.random() * dh * 0.5
            sr = rng.random() * 1.5 + 0.3
            canvas.drawCircle(sx, sy, sr, paint)

    def toggle_freeze(self):
        self.frozen = not self.frozen
        self.color_name = ("❄ Frozen — " + self.hex_color) if self.frozen else self._color_name_from_hex()

    def _color_name_from_hex(self):
        return self.color_name

    def switch_camera(self):
        self.front_camera = not self.front_camera
        cam = self.ids.get("cam")
        if cam:
            cam.play = False
            cam.index = 1 if self.front_camera else 0
            cam.play = self.cam_active

    def set_mode(self, mode):
        self.mode = mode

    def set_speed(self, level):
        self.speed_ms = self.SPEED_MS.get(level, 1000)
        label = self.ids.get("speed_label")
        if label:
            label.text = self.SPEED_LABELS.get(level, "Normal")

    def _color_name(self, h, s, l):
        if s < 0.12:
            if l < 0.20: return "Deep Black"
            if l > 0.80: return "Pure White"
            return "Neutral Gray"
        if l < 0.10: return "Midnight Dark"
        if l > 0.92: return "Bright White"
        hd = int(h * 360)
        names = [
            (0,  15,  "Crimson Red"),   (15, 30,  "Sunset Orange"),
            (30, 45,  "Amber Glow"),    (45, 65,  "Golden Yellow"),
            (65, 80,  "Lime Green"),    (80, 150, "Forest Green"),
            (150,175, "Emerald Teal"),  (175,200, "Aqua Cyan"),
            (200,230, "Ocean Blue"),    (230,260, "Deep Cobalt"),
            (260,280, "Royal Indigo"),  (280,310, "Violet Purple"),
            (310,340, "Magenta Rose"),  (340,361, "Crimson Red"),
        ]
        for lo, hi, name in names:
            if lo <= hd < hi:
                return name
        return "Pure Hue"


# ── App class ───────────────────────────────────────────────────────────────
class ChameleonApp(App):
    def build(self):
        Window.softinput_mode = "below_target"
        if platform == "android":
            from android.runnable import run_on_ui_thread
            Window.borderless = True

        from kivy.uix.boxlayout import BoxLayout
        # Patch root class bases
        ChameleonRoot.__bases__ = (BoxLayout,)

        root = Builder.load_string(KV)
        # Builder returns the last widget — we need ChameleonRoot
        # Build manually since KV root is ChameleonRoot
        return root

    def on_stop(self):
        pass


if __name__ == "__main__":
    ChameleonApp().run()
