"""
🦎 Chameleon Wallpaper — Streamlit App
Run with:  streamlit run streamlit_app.py
"""

import io
import time
from colorsys import rgb_to_hls, hls_to_rgb

import numpy as np
import streamlit as st
from PIL import Image, ImageDraw, ImageFilter

# ── Page config ─────────────────────────────────────────────────────────────
st.set_page_config(
    page_title="Chameleon Wallpaper",
    page_icon="🦎",
    layout="centered",
    initial_sidebar_state="collapsed",
)

# ── Custom CSS ───────────────────────────────────────────────────────────────
st.markdown("""
<style>
  @import url('https://fonts.googleapis.com/css2?family=DM+Sans:wght@300;400;600&family=DM+Mono:wght@400&display=swap');

  html, body, [data-testid="stAppViewContainer"] {
    font-family: 'DM Sans', sans-serif;
  }
  [data-testid="stAppViewContainer"] {
    background: #0d0d1a;
  }
  [data-testid="stHeader"] { background: transparent; }
  [data-testid="stSidebar"] { background: #0d0d1a; }

  .hero-card {
    background: linear-gradient(135deg, #1a1a2e 0%, #16213e 100%);
    border: 1px solid rgba(255,255,255,0.1);
    border-radius: 24px;
    padding: 28px 24px 20px;
    text-align: center;
    margin-bottom: 20px;
  }
  .swatch-circle {
    width: 120px; height: 120px;
    border-radius: 50%;
    margin: 0 auto 16px;
    border: 2px solid rgba(255,255,255,0.15);
    transition: background 0.8s ease;
  }
  .hex-label {
    font-family: 'DM Mono', monospace;
    font-size: 2rem;
    font-weight: 400;
    color: #fff;
    letter-spacing: 2px;
    margin: 0;
  }
  .name-label {
    font-size: 0.85rem;
    color: rgba(255,255,255,0.45);
    margin: 6px 0 0;
    letter-spacing: 0.5px;
  }
  .palette-row {
    display: flex;
    gap: 10px;
    justify-content: center;
    flex-wrap: wrap;
    margin: 14px 0;
  }
  .pal-dot {
    width: 38px; height: 38px;
    border-radius: 12px;
    border: 1px solid rgba(255,255,255,0.12);
    display: inline-block;
  }
  .ctrl-card {
    background: rgba(255,255,255,0.05);
    border: 1px solid rgba(255,255,255,0.08);
    border-radius: 18px;
    padding: 18px 20px;
    margin-bottom: 14px;
  }
  .section-label {
    font-size: 0.7rem;
    font-weight: 600;
    letter-spacing: 1.5px;
    color: rgba(255,255,255,0.35);
    text-transform: uppercase;
    margin-bottom: 10px;
  }
  .status-pill {
    display: inline-flex;
    align-items: center;
    gap: 7px;
    background: rgba(0,0,0,0.4);
    border: 1px solid rgba(255,255,255,0.12);
    border-radius: 100px;
    padding: 5px 14px;
    font-size: 0.72rem;
    font-weight: 600;
    color: rgba(255,255,255,0.8);
    letter-spacing: 0.5px;
    margin-bottom: 20px;
  }
  .dot-active   { width:8px; height:8px; border-radius:50%; background:#22c55e; display:inline-block; }
  .dot-inactive { width:8px; height:8px; border-radius:50%; background:#ef4444; display:inline-block; }
  .brightness-bar {
    background: rgba(255,255,255,0.1);
    border-radius: 4px;
    height: 4px;
    margin-top: 10px;
    overflow: hidden;
  }
  .brightness-fill {
    height: 100%;
    border-radius: 4px;
    background: rgba(255,255,255,0.7);
  }
  .stButton > button {
    font-family: 'DM Sans', sans-serif !important;
    border-radius: 14px !important;
    font-weight: 500 !important;
    border: 1px solid rgba(255,255,255,0.15) !important;
    background: rgba(255,255,255,0.07) !important;
    color: rgba(255,255,255,0.85) !important;
    width: 100% !important;
  }
  .stButton > button:hover {
    background: rgba(255,255,255,0.13) !important;
    border-color: rgba(255,255,255,0.3) !important;
  }
  .stDownloadButton > button {
    border-radius: 14px !important;
    font-family: 'DM Sans', sans-serif !important;
    font-weight: 600 !important;
    background: #22c55e !important;
    color: #000 !important;
    border: none !important;
    width: 100% !important;
  }
  label, .stSelectbox label, .stSlider label {
    color: rgba(255,255,255,0.5) !important;
    font-size: 0.78rem !important;
    text-transform: uppercase !important;
    letter-spacing: 1px !important;
  }
  [data-testid="stCameraInput"] label {
    color: rgba(255,255,255,0.7) !important;
    font-size: 0.95rem !important;
    text-transform: none !important;
    letter-spacing: 0px !important;
  }
  .stSelectbox > div > div {
    background: rgba(255,255,255,0.07) !important;
    border: 1px solid rgba(255,255,255,0.12) !important;
    border-radius: 12px !important;
    color: #fff !important;
  }
  .big-title {
    font-size: 1.5rem;
    font-weight: 600;
    color: #fff;
    margin: 0 0 4px;
  }
  .sub-title {
    font-size: 0.85rem;
    color: rgba(255,255,255,0.4);
    margin-bottom: 20px;
  }
  footer { display: none; }
  #MainMenu { display: none; }
</style>
""", unsafe_allow_html=True)


# ── Color utilities ──────────────────────────────────────────────────────────
def extract_dominant(img: Image.Image):
    small = img.resize((40, 30), Image.LANCZOS).convert("RGB")
    arr = np.array(small).reshape(-1, 3)
    return tuple(arr.mean(axis=0).astype(int))


def color_name(h, s, l):
    if s < 0.12:
        if l < 0.20: return "Deep Black"
        if l > 0.80: return "Pure White"
        return "Neutral Gray"
    if l < 0.10: return "Midnight Dark"
    if l > 0.92: return "Bright White"
    hd = int(h * 360)
    table = [
        (0,15,"Crimson Red"),(15,30,"Sunset Orange"),(30,45,"Amber Glow"),
        (45,65,"Golden Yellow"),(65,80,"Lime Chartreuse"),(80,150,"Forest Green"),
        (150,175,"Emerald Teal"),(175,200,"Aqua Cyan"),(200,230,"Ocean Blue"),
        (230,260,"Deep Cobalt"),(260,280,"Royal Indigo"),(280,310,"Violet Purple"),
        (310,340,"Magenta Rose"),(340,361,"Crimson Red"),
    ]
    for lo, hi, name in table:
        if lo <= hd < hi:
            return name
    return "Pure Hue"


def hls_color(h, l, s):
    return tuple(int(c * 255) for c in hls_to_rgb(h, l, s))


# ── Wallpaper renderers ──────────────────────────────────────────────────────
W, H = 1080, 1920

def render_solid(r, g, b, h, l, s) -> Image.Image:
    dark_l = max(0.03, l - 0.18)
    bg = hls_color(h, dark_l, s)
    img = Image.new("RGB", (W, H), bg)
    # Vignette via radial gradient overlay
    vig = Image.new("RGBA", (W, H), (0, 0, 0, 0))
    draw = ImageDraw.Draw(vig)
    cx, cy = W // 2, H // 2
    for i in range(min(W, H) // 2, 0, -5):
        alpha = int(180 * (1 - i / (min(W, H) * 0.6)))
        alpha = max(0, min(200, alpha))
        draw.ellipse([cx - i, cy - i, cx + i, cy + i], fill=(0, 0, 0, alpha))
    img = Image.alpha_composite(img.convert("RGBA"), vig).convert("RGB")
    return img


def render_gradient(r, g, b, h, l, s) -> Image.Image:
    dark_l = max(0.03, l - 0.22)
    bg = hls_color(h, dark_l, min(s, 0.8))
    img = Image.new("RGB", (W, H), bg)
    overlay = Image.new("RGBA", (W, H), (0, 0, 0, 0))

    def radial_blob(cx, cy, radius, color_rgb, alpha_center=160):
        blob = Image.new("RGBA", (W, H), (0, 0, 0, 0))
        draw = ImageDraw.Draw(blob)
        steps = radius // 8
        for i in range(steps, 0, -1):
            a = int(alpha_center * (i / steps))
            r2 = int(radius * i / steps)
            draw.ellipse([cx - r2, cy - r2, cx + r2, cy + r2],
                         fill=(*color_rgb, a))
        return blob

    c1 = hls_color(h, min(0.75, l + 0.2), s)
    overlay = Image.alpha_composite(overlay, radial_blob(int(W * 0.2), int(H * 0.2), int(W * 0.8), c1))

    h2 = (h + 0.08) % 1.0
    c2 = hls_color(h2, min(0.65, l + 0.1), s)
    overlay = Image.alpha_composite(overlay, radial_blob(int(W * 0.8), int(H * 0.75), int(W * 0.7), c2, 140))

    overlay = Image.alpha_composite(overlay, radial_blob(W // 2, int(H * 0.35), int(W * 0.45), (255, 255, 255), 55))

    # Vignette
    vig = Image.new("RGBA", (W, H), (0, 0, 0, 0))
    vdraw = ImageDraw.Draw(vig)
    cx, cy = W // 2, H // 2
    for i in range(max(W, H), 0, -10):
        ratio = i / max(W, H)
        if ratio > 0.35:
            a = int(160 * (1 - ratio) / 0.65)
            vdraw.ellipse([cx - i, cy - i, cx + i, cy + i], fill=(0, 0, 0, max(0, 160 - a)))

    img = Image.alpha_composite(img.convert("RGBA"), overlay)
    img = Image.alpha_composite(img, vig).convert("RGB")
    return img


def render_aurora(r, g, b, h, l, s) -> Image.Image:
    import random
    dark_l = max(0.03, l - 0.25)
    bg = hls_color(h, dark_l, min(s, 0.7))
    img = Image.new("RGB", (W, H), bg)
    overlay = Image.new("RGBA", (W, H), (0, 0, 0, 0))
    draw = ImageDraw.Draw(overlay)

    # Aurora bands
    band_hues = [h, (h + 0.11) % 1.0, (h + 0.25) % 1.0, (h + 0.42) % 1.0]
    for i, bh in enumerate(band_hues):
        y_pos = int(H * (0.2 + i * 0.18))
        band_h = int(H * 0.22)
        bc = hls_color(bh, min(0.70, l + 0.25), min(0.95, s + 0.2))
        band = Image.new("RGBA", (W, band_h * 2), (0, 0, 0, 0))
        band_draw = ImageDraw.Draw(band)
        for row in range(band_h * 2):
            dist = abs(row - band_h) / band_h
            a = int(120 * max(0, 1 - dist))
            band_draw.line([(0, row), (W, row)], fill=(*bc, a))
        overlay.alpha_composite(band, (0, y_pos - band_h))

    img = Image.alpha_composite(img.convert("RGBA"), overlay)
    # Stars
    star_layer = Image.new("RGBA", (W, H), (0, 0, 0, 0))
    sdraw = ImageDraw.Draw(star_layer)
    rng = random.Random(42)
    for _ in range(150):
        sx = int(rng.random() * W)
        sy = int(rng.random() * H * 0.55)
        sr = rng.random() * 1.5 + 0.3
        a = int(rng.random() * 120 + 60)
        sdraw.ellipse([sx - sr, sy - sr, sx + sr, sy + sr], fill=(255, 255, 255, a))
    img = Image.alpha_composite(img, star_layer).convert("RGB")
    return img


RENDERERS = {"Solid": render_solid, "Gradient": render_gradient, "Aurora": render_aurora}


def img_to_bytes(img: Image.Image) -> bytes:
    buf = io.BytesIO()
    img.save(buf, format="PNG")
    return buf.getvalue()


# ── Session state ────────────────────────────────────────────────────────────
if "palette" not in st.session_state:
    st.session_state.palette = []
if "last_rgb" not in st.session_state:
    st.session_state.last_rgb = (30, 30, 80)
if "frozen" not in st.session_state:
    st.session_state.frozen = False


# ── Header ───────────────────────────────────────────────────────────────────
st.markdown("""
<div style='text-align:center; padding: 24px 0 8px;'>
  <div class='big-title'>🦎 Chameleon Wallpaper</div>
  <div class='sub-title'>Snap → extract color → download your wallpaper</div>
</div>
""", unsafe_allow_html=True)

# ── Camera input ─────────────────────────────────────────────────────────────
cam_img = st.camera_input("📷 Point camera at any surface and capture", key="camera")

# ── Process frame ─────────────────────────────────────────────────────────────
if cam_img and not st.session_state.frozen:
    frame = Image.open(cam_img)
    r, g, b = extract_dominant(frame)
    st.session_state.last_rgb = (r, g, b)
    # Add to palette
    hex_val = "#{:02X}{:02X}{:02X}".format(r, g, b)
    if not st.session_state.palette or st.session_state.palette[0] != hex_val:
        st.session_state.palette.insert(0, hex_val)
        st.session_state.palette = st.session_state.palette[:7]

r, g, b = st.session_state.last_rgb
rf, gf, bf = r / 255.0, g / 255.0, b / 255.0
h, l, s = rgb_to_hls(rf, gf, bf)
hex_val  = "#{:02X}{:02X}{:02X}".format(r, g, b)
cname    = color_name(h, s, l)
brightness = int((0.299 * r + 0.587 * g + 0.114 * b) / 255 * 100)

# ── Hero card ────────────────────────────────────────────────────────────────
frozen_badge = " ❄" if st.session_state.frozen else ""
st.markdown(f"""
<div class='hero-card'>
  <div class='swatch-circle' style='background:rgb({r},{g},{b});'></div>
  <p class='hex-label'>{hex_val}{frozen_badge}</p>
  <p class='name-label'>{cname}</p>
  <div class='brightness-bar'>
    <div class='brightness-fill' style='width:{brightness}%; background:rgb({r},{g},{b});'></div>
  </div>
  <p style='font-size:0.68rem;color:rgba(255,255,255,0.3);margin:6px 0 0;'>Brightness {brightness}%</p>
</div>
""", unsafe_allow_html=True)

# ── Palette ───────────────────────────────────────────────────────────────────
if st.session_state.palette:
    dots = "".join(
        f"<span class='pal-dot' style='background:{c};' title='{c}'></span>"
        for c in st.session_state.palette
    )
    st.markdown(f"""
    <div class='ctrl-card'>
      <div class='section-label'>Color History</div>
      <div class='palette-row'>{dots}</div>
    </div>
    """, unsafe_allow_html=True)

# ── Controls ──────────────────────────────────────────────────────────────────
col1, col2 = st.columns(2)

with col1:
    st.markdown("<div class='section-label' style='color:rgba(255,255,255,0.35);font-size:0.7rem;letter-spacing:1.5px;text-transform:uppercase;'>Wallpaper Style</div>", unsafe_allow_html=True)
    mode = st.selectbox("", ["Gradient", "Solid", "Aurora"], label_visibility="collapsed")

with col2:
    st.markdown("<div class='section-label' style='color:rgba(255,255,255,0.35);font-size:0.7rem;letter-spacing:1.5px;text-transform:uppercase;'>Wallpaper Size</div>", unsafe_allow_html=True)
    size_opt = st.selectbox("", ["1080×1920 (FHD)", "1440×2560 (QHD)", "1170×2532 (iPhone 14)"], label_visibility="collapsed")

SIZE_MAP = {
    "1080×1920 (FHD)":       (1080, 1920),
    "1440×2560 (QHD)":       (1440, 2560),
    "1170×2532 (iPhone 14)": (1170, 2532),
}
W, H = SIZE_MAP[size_opt]

# Freeze toggle
col3, col4 = st.columns(2)
with col3:
    if st.button("❄  Freeze Color" if not st.session_state.frozen else "▶  Unfreeze", use_container_width=True):
        st.session_state.frozen = not st.session_state.frozen
        st.rerun()
with col4:
    if st.button("🗑  Clear Palette", use_container_width=True):
        st.session_state.palette = []
        st.rerun()

# ── Generate + Download wallpaper ─────────────────────────────────────────────
st.markdown("---")
st.markdown("<div style='text-align:center;color:rgba(255,255,255,0.5);font-size:0.8rem;margin-bottom:14px;'>Generate & Download Wallpaper</div>", unsafe_allow_html=True)

if st.button("🎨  Generate Wallpaper Now", use_container_width=True):
    with st.spinner("Rendering your wallpaper…"):
        renderer = RENDERERS[mode]
        wall = renderer(r, g, b, h, l, s)
        wall = wall.resize((W, H), Image.LANCZOS)
        wall_bytes = img_to_bytes(wall)

    st.image(wall, caption=f"{mode} · {hex_val} · {cname}", use_container_width=True)

    st.download_button(
        label=f"⬇  Download {mode} Wallpaper  ({W}×{H})",
        data=wall_bytes,
        file_name=f"chameleon_{hex_val.strip('#')}_{mode.lower()}_{W}x{H}.png",
        mime="image/png",
        use_container_width=True,
    )

# ── Footer tip ────────────────────────────────────────────────────────────────
st.markdown("""
<div style='text-align:center;padding:28px 0 10px;color:rgba(255,255,255,0.2);font-size:0.72rem;'>
  📱 For a true live wallpaper, use the Android app version
</div>
""", unsafe_allow_html=True)
