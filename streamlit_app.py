"""
🦎 Chameleon Wallpaper — Real-time, full-color, multi-color aurora
"""
import io, threading, time, random
from colorsys import rgb_to_hls, hls_to_rgb

import av
import numpy as np
import streamlit as st
from PIL import Image, ImageDraw, ImageFilter
from streamlit_webrtc import webrtc_streamer, WebRtcMode, RTCConfiguration

st.set_page_config(page_title="Chameleon Wallpaper", page_icon="🦎",
                   layout="centered", initial_sidebar_state="collapsed")

st.markdown("""
<style>
@import url('https://fonts.googleapis.com/css2?family=DM+Sans:wght@300;400;600&family=DM+Mono:wght@400&display=swap');
html,body,[data-testid="stAppViewContainer"]{font-family:'DM Sans',sans-serif;background:#000!important;}
[data-testid="stHeader"]{background:transparent!important;}
[data-testid="stMainBlockContainer"]{padding-top:.5rem!important;}
footer,#MainMenu{display:none!important;}
.hero{border-radius:24px;padding:24px 18px 20px;margin-bottom:14px;text-align:center;}
.swatch-row{display:flex;gap:10px;justify-content:center;margin-bottom:14px;}
.swatch-circle{width:64px;height:64px;border-radius:50%;border:2px solid rgba(255,255,255,.2);flex-shrink:0;}
.hex-txt{font-family:'DM Mono',monospace;font-size:1.7rem;color:#fff;letter-spacing:2px;margin:0;}
.name-txt{font-size:.8rem;color:rgba(255,255,255,.45);margin:5px 0 0;}
.palette-row{display:flex;gap:8px;justify-content:center;flex-wrap:wrap;margin:12px 0 2px;}
.pal-dot{width:34px;height:34px;border-radius:10px;border:1px solid rgba(255,255,255,.12);display:inline-block;}
.card{background:rgba(255,255,255,.05);border:1px solid rgba(255,255,255,.08);border-radius:18px;padding:14px 16px;margin-bottom:10px;}
.sec-label{font-size:.65rem;font-weight:600;letter-spacing:1.5px;color:rgba(255,255,255,.3);text-transform:uppercase;margin-bottom:8px;}
.live-badge{display:inline-flex;align-items:center;gap:7px;background:rgba(0,0,0,.5);border:1px solid rgba(255,255,255,.12);border-radius:100px;padding:5px 14px;font-size:.7rem;font-weight:600;color:rgba(255,255,255,.8);letter-spacing:.8px;margin-bottom:16px;}
.dot{width:8px;height:8px;border-radius:50%;display:inline-block;}
.dot-green{background:#22c55e;animation:blink 1.8s infinite;}
.dot-red{background:#ef4444;}
.multi-label{font-size:.7rem;color:rgba(255,255,255,.5);background:rgba(255,255,255,.08);border-radius:8px;padding:3px 10px;display:inline-block;margin-top:6px;}
@keyframes blink{0%,100%{opacity:1}50%{opacity:.35}}
.stButton>button{font-family:'DM Sans',sans-serif!important;border-radius:14px!important;font-weight:500!important;border:1px solid rgba(255,255,255,.15)!important;background:rgba(255,255,255,.07)!important;color:rgba(255,255,255,.85)!important;width:100%!important;}
.stButton>button:hover{background:rgba(255,255,255,.14)!important;}
.stDownloadButton>button{border-radius:14px!important;font-weight:600!important;background:#22c55e!important;color:#000!important;border:none!important;width:100%!important;}
div[data-testid="stSelectbox"]>div>div{background:rgba(255,255,255,.07)!important;border:1px solid rgba(255,255,255,.12)!important;border-radius:12px!important;color:#fff!important;}
label{color:rgba(255,255,255,.4)!important;font-size:.72rem!important;text-transform:uppercase!important;letter-spacing:1px!important;}
</style>
""", unsafe_allow_html=True)

# ── Session state ─────────────────────────────────────────────────────────────
for k,v in [("colors",[(30,30,80)]),("palette",[]),("frozen",False),("mode","Auto")]:
    if k not in st.session_state: st.session_state[k] = v

_lock = threading.Lock()
_frame_colors = [[30,30,80]]   # list of up to 5 dominant colors from latest frame

# ── Color extraction — k-means style dominant colors ─────────────────────────
def extract_colors(frame_rgb: np.ndarray, n=5):
    """Extract up to n dominant colors using quantization."""
    h, w = frame_rgb.shape[:2]
    small = frame_rgb[::max(1,h//40), ::max(1,w//40)].reshape(-1,3).astype(np.float32)

    # Simple quantize: bucket into 8x8x8 color cubes, pick top n buckets
    buckets = {}
    for px in small:
        key = (int(px[0])>>5, int(px[1])>>5, int(px[2])>>5)
        if key not in buckets: buckets[key] = [0, 0, 0, 0]
        buckets[key][0] += px[0]; buckets[key][1] += px[1]
        buckets[key][2] += px[2]; buckets[key][3] += 1

    # Sort by count, filter out near-black/near-white buckets for color variety
    sorted_b = sorted(buckets.values(), key=lambda x: -x[3])
    colors = []
    for b in sorted_b:
        if b[3] == 0: continue
        r,g,bv = int(b[0]/b[3]), int(b[1]/b[3]), int(b[2]/b[3])
        # Check it's different enough from already-picked colors
        if all(abs(r-c[0])+abs(g-c[1])+abs(bv-c[2]) > 60 for c in colors):
            colors.append((r, g, bv))
        if len(colors) >= n: break

    return colors if colors else [(30,30,80)]

def colors_are_distinct(colors, threshold=80):
    """True if the colors differ enough to warrant aurora mode."""
    if len(colors) < 2: return False
    for i in range(len(colors)):
        for j in range(i+1, len(colors)):
            diff = sum(abs(colors[i][k]-colors[j][k]) for k in range(3))
            if diff > threshold: return True
    return False

def color_name_rgb(r, g, b):
    rf,gf,bf = r/255,g/255,b/255
    h,l,s = rgb_to_hls(rf,gf,bf)
    if s < 0.12:
        return "Deep Black" if l<.20 else ("Pure White" if l>.80 else "Neutral Gray")
    if l < 0.10: return "Midnight Dark"
    hd = int(h*360)
    for lo,hi,n in [(0,15,"Crimson Red"),(15,30,"Sunset Orange"),(30,45,"Amber Glow"),
                    (45,65,"Golden Yellow"),(65,80,"Lime Green"),(80,150,"Forest Green"),
                    (150,175,"Emerald Teal"),(175,200,"Aqua Cyan"),(200,230,"Ocean Blue"),
                    (230,260,"Deep Cobalt"),(260,280,"Royal Indigo"),(280,310,"Violet Purple"),
                    (310,340,"Magenta Rose"),(340,361,"Crimson Red")]:
        if lo<=hd<hi: return n
    return "Pure Hue"

def hls_c(h,l,s):
    return tuple(max(0,min(255,int(c*255))) for c in hls_to_rgb(h,l,s))

# ── Wallpaper renderers ───────────────────────────────────────────────────────
WW, WH = 1080, 1920

def make_bitmap(size=(WW,WH)):
    return Image.new("RGBA", size, (0,0,0,255))

def radial(cx, cy, r, color, alpha=200, img_size=(WW,WH)):
    layer = Image.new("RGBA", img_size, (0,0,0,0))
    d = ImageDraw.Draw(layer)
    steps = max(1, r//4)
    for i in range(steps, 0, -1):
        a  = int(alpha * (i/steps)**1.2)
        r2 = int(r * i/steps)
        d.ellipse([cx-r2,cy-r2,cx+r2,cy+r2], fill=(*color,a))
    return layer

def render_single(colors):
    """One dominant color — rich full-screen gradient."""
    r,g,b = colors[0]
    rf,gf,bf = r/255,g/255,b/255
    h,l,s = rgb_to_hls(rf,gf,bf)
    # Boost saturation for vivid result
    s = min(1.0, s*1.4 + 0.2)
    l_mid = min(0.55, max(0.3, l))

    bg = hls_c(h, max(0.04, l_mid-0.22), s)
    img = Image.new("RGBA",(WW,WH), (*bg,255))

    # Large central blob — the main color, very bright
    c_bright = hls_c(h, min(0.75, l_mid+0.25), s)
    img = Image.alpha_composite(img, radial(WW//2, WH//2, int(WW*1.1), c_bright, 210))

    # Top blob
    c_top = hls_c((h+0.03)%1, min(0.85, l_mid+0.35), s)
    img = Image.alpha_composite(img, radial(int(WW*0.3), int(WH*0.15), int(WW*0.75), c_top, 180))

    # Bottom blob
    c_bot = hls_c((h-0.03)%1, max(0.1, l_mid-0.1), min(1,s*1.1))
    img = Image.alpha_composite(img, radial(int(WW*0.7), int(WH*0.85), int(WW*0.75), c_bot, 180))

    # Subtle white shimmer center
    img = Image.alpha_composite(img, radial(WW//2, WH//2, int(WW*0.35), (255,255,255), 35))

    return img.convert("RGB")

def render_aurora_multi(colors):
    """Multiple colors — full aurora bands across the whole screen."""
    # Use up to 5 colors
    cols = colors[:5]
    n = len(cols)

    # Dark background from first color
    r0,g0,b0 = cols[0]
    h0,l0,s0 = rgb_to_hls(r0/255,g0/255,b0/255)
    bg = hls_c(h0, max(0.03, l0*0.25), min(s0*0.8,0.7))
    img = Image.new("RGBA",(WW,WH),(*bg,255))

    # Full-height color zones — each color owns a vertical band of the screen
    zone_h = WH // n
    for i, (r,g,b) in enumerate(cols):
        rf,gf,bf = r/255,g/255,b/255
        h,l,s = rgb_to_hls(rf,gf,bf)
        s = min(1.0, s*1.5+0.25)  # boost saturation hard
        l_vivid = min(0.72, max(0.35, l+0.2))

        yc = int(zone_h*i + zone_h*0.5)
        c_vivid = hls_c(h, l_vivid, s)

        # Wide horizontal band
        band = Image.new("RGBA",(WW, WH),(0,0,0,0))
        bd = ImageDraw.Draw(band)
        band_half = int(zone_h * 0.75)
        for row in range(WH):
            dist = abs(row - yc)
            if dist < band_half*1.5:
                a = int(230 * max(0, 1 - (dist/(band_half*1.5))**0.7))
                bd.line([(0,row),(WW,row)], fill=(*c_vivid, a))
        img = Image.alpha_composite(img, band)

        # Bright center blob per color
        c_bright = hls_c(h, min(0.88, l_vivid+0.18), s)
        xc = int(WW * (0.25 + 0.5 * ((i+0.5)/n)))
        img = Image.alpha_composite(img, radial(xc, yc, int(WW*0.55), c_bright, 160))

    # Blending sweep — soft left-to-right diagonal blend
    for i, (r,g,b) in enumerate(cols[:-1]):
        r2,g2,b2 = cols[i+1]
        blend_y = int(zone_h*(i+1))
        rf,gf,bf = (r+r2)//2/255,(g+g2)//2/255,(b+b2)//2/255
        h,l,s = rgb_to_hls(rf,gf,bf)
        s = min(1.0,s*1.6+0.3)
        blend_c = hls_c(h, min(0.8,l+0.3), s)
        img = Image.alpha_composite(img, radial(WW//2, blend_y, int(WW*0.45), blend_c, 120))

    # Star field
    star = Image.new("RGBA",(WW,WH),(0,0,0,0))
    sd = ImageDraw.Draw(star)
    rng = random.Random(42)
    for _ in range(200):
        sx=int(rng.random()*WW); sy=int(rng.random()*WH)
        sr=rng.random()*1.8+0.2
        sd.ellipse([sx-sr,sy-sr,sx+sr,sy+sr],
                   fill=(255,255,255,int(rng.random()*90+30)))
    img = Image.alpha_composite(img, star)

    # Final soft blur for cinematic blending
    blurred = img.filter(ImageFilter.GaussianBlur(radius=18))
    return Image.blend(img.convert("RGB"), blurred.convert("RGB"), 0.35)

def render_wallpaper(colors, force_mode="Auto"):
    multi = colors_are_distinct(colors)
    if force_mode == "Auto":
        use_aurora = multi and len(colors) >= 2
    elif force_mode == "Aurora":
        use_aurora = True
    else:
        use_aurora = False

    if use_aurora:
        return render_aurora_multi(colors), True
    else:
        return render_single(colors), False

def img_bytes(img):
    buf=io.BytesIO(); img.save(buf,format="PNG"); return buf.getvalue()

# ── WebRTC callback ───────────────────────────────────────────────────────────
def video_frame_callback(frame: av.VideoFrame) -> av.VideoFrame:
    if not st.session_state.get("frozen", False):
        arr = frame.to_ndarray(format="rgb24")
        cols = extract_colors(arr, n=5)
        with _lock:
            _frame_colors.clear()
            _frame_colors.extend(cols)
    return frame

# ── UI ────────────────────────────────────────────────────────────────────────
st.markdown("""
<div style='text-align:center;padding:16px 0 4px;'>
  <span style='font-size:2rem;'>🦎</span>
  <div style='font-size:1.4rem;font-weight:600;color:#fff;margin:4px 0 2px;'>Chameleon Wallpaper</div>
  <div style='font-size:.78rem;color:rgba(255,255,255,.3);'>Real-time camera → full color wallpaper • multi-color aurora</div>
</div>
""", unsafe_allow_html=True)

ctx = webrtc_streamer(
    key="chameleon",
    mode=WebRtcMode.SENDONLY,
    video_frame_callback=video_frame_callback,
    rtc_configuration=RTCConfiguration({"iceServers":[{"urls":["stun:stun.l.google.com:19302"]}]}),
    media_stream_constraints={"video":{"width":320,"height":240},"audio":False},
    async_processing=True,
)
is_live = ctx.state.playing if ctx else False

c1,c2,c3 = st.columns(3)
with c1:
    mode = st.selectbox("Style", ["Auto","Aurora","Gradient"])
    st.session_state.mode = mode
with c2:
    sz = st.selectbox("Size", ["1080×1920","1440×2560","1170×2532 (iPhone)"])
with c3:
    if st.button("❄ Unfreeze" if st.session_state.frozen else "❄ Freeze", use_container_width=True):
        st.session_state.frozen = not st.session_state.frozen
        st.rerun()

SZ={"1080×1920":(1080,1920),"1440×2560":(1440,2560),"1170×2532 (iPhone)":(1170,2532)}

hero_sl = st.empty()
pal_sl  = st.empty()
wall_sl = st.empty()
dl_sl   = st.empty()

def render_ui(colors):
    r,g,b = colors[0]
    hex_v = f"#{r:02X}{g:02X}{b:02X}"
    cnames = [color_name_rgb(*c) for c in colors[:3]]
    multi = colors_are_distinct(colors)
    fb = " ❄" if st.session_state.frozen else ""

    # Swatches row
    swatches = "".join(
        f"<div class='swatch-circle' style='background:rgb{c};width:{'64' if i==0 else '48'}px;height:{'64' if i==0 else '48'}px;margin-top:{'0' if i==0 else '8'}px'></div>"
        for i,c in enumerate(colors[:4])
    )

    mode_info = ""
    if multi:
        mode_info = f"<div class='multi-label'>🌈 {len(colors)} colors detected → Aurora mode</div>"

    dark_bg = f"rgb({max(0,int(r*.12))},{max(0,int(g*.12))},{max(0,int(b*.12))})"
    hero_sl.markdown(f"""
<div class="hero" style="background:{dark_bg};">
  <div class="live-badge">
    <span class="dot {'dot-green' if is_live else 'dot-red'}"></span>
    {'LIVE' if is_live else 'CAMERA OFF'}
  </div>
  <div class="swatch-row">{swatches}</div>
  <p class="hex-txt">{hex_v}{fb}</p>
  <p class="name-txt">{' · '.join(cnames)}</p>
  {mode_info}
</div>""", unsafe_allow_html=True)

    pal = st.session_state.palette
    if pal:
        dots="".join(f"<span class='pal-dot' style='background:{c};'></span>" for c in pal)
        pal_sl.markdown(f"<div class='card'><div class='sec-label'>Color history</div><div class='palette-row'>{dots}</div></div>",
                        unsafe_allow_html=True)

    wall_img, used_aurora = render_wallpaper(colors, force_mode=st.session_state.mode)
    preview = wall_img.resize((360,640), Image.LANCZOS)
    cap = f"{'Aurora' if used_aurora else 'Gradient'}  •  {hex_v}  •  {' + '.join(cnames[:2])}"
    wall_sl.image(preview, use_container_width=True, caption=cap)

    tw,th = SZ[sz]
    full = wall_img.resize((tw,th), Image.LANCZOS)
    dl_sl.download_button(
        label=f"⬇  Download Wallpaper  ({sz})",
        data=img_bytes(full),
        file_name=f"chameleon_{hex_v.strip('#')}_{'aurora' if used_aurora else 'gradient'}.png",
        mime="image/png",
        use_container_width=True,
    )

# ── Loop ──────────────────────────────────────────────────────────────────────
if is_live:
    with _lock:
        colors = list(tuple(c) for c in _frame_colors)
    st.session_state.colors = colors

    # Update palette
    hex_v = f"#{colors[0][0]:02X}{colors[0][1]:02X}{colors[0][2]:02X}"
    if not st.session_state.palette or st.session_state.palette[0] != hex_v:
        st.session_state.palette.insert(0, hex_v)
        st.session_state.palette = st.session_state.palette[:8]

    render_ui(colors)
    time.sleep(0.8)
    st.rerun()
else:
    render_ui(st.session_state.colors)
    st.markdown("""<div style='text-align:center;padding:10px;color:rgba(255,255,255,.3);font-size:.78rem;'>
      ☝️ Click <b style='color:rgba(255,255,255,.6)'>START</b> above to activate live camera
    </div>""", unsafe_allow_html=True)

st.markdown("<div style='text-align:center;padding:18px 0 4px;color:rgba(255,255,255,.12);font-size:.65rem;'>🦎 Chameleon Wallpaper</div>",
            unsafe_allow_html=True)
