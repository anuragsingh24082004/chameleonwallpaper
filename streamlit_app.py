"""
🦎 Chameleon Wallpaper — Smooth debounced color detection
Waits 3-5s of stable color before switching wallpaper.
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
.hero{border-radius:24px;padding:24px 18px 20px;margin-bottom:14px;text-align:center;transition:background 2s ease;}
.swatch-row{display:flex;gap:10px;justify-content:center;align-items:center;margin-bottom:14px;}
.swatch-circle{border-radius:50%;border:2px solid rgba(255,255,255,.2);flex-shrink:0;}
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
.dot-yellow{background:#f59e0b;animation:blink 1s infinite;}
.multi-label{font-size:.7rem;color:rgba(255,255,255,.5);background:rgba(255,255,255,.08);border-radius:8px;padding:3px 10px;display:inline-block;margin-top:6px;}
.progress-wrap{background:rgba(255,255,255,.1);border-radius:100px;height:3px;margin:10px auto;max-width:200px;overflow:hidden;}
.progress-fill{height:100%;border-radius:100px;background:#22c55e;transition:width .3s ease;}
.status-txt{font-size:.68rem;color:rgba(255,255,255,.35);margin-top:5px;}
@keyframes blink{0%,100%{opacity:1}50%{opacity:.35}}
.stButton>button{font-family:'DM Sans',sans-serif!important;border-radius:14px!important;font-weight:500!important;border:1px solid rgba(255,255,255,.15)!important;background:rgba(255,255,255,.07)!important;color:rgba(255,255,255,.85)!important;width:100%!important;}
.stButton>button:hover{background:rgba(255,255,255,.14)!important;}
.stDownloadButton>button{border-radius:14px!important;font-weight:600!important;background:#22c55e!important;color:#000!important;border:none!important;width:100%!important;}
div[data-testid="stSelectbox"]>div>div{background:rgba(255,255,255,.07)!important;border:1px solid rgba(255,255,255,.12)!important;border-radius:12px!important;color:#fff!important;}
label{color:rgba(255,255,255,.4)!important;font-size:.72rem!important;text-transform:uppercase!important;letter-spacing:1px!important;}
</style>
""", unsafe_allow_html=True)

# ── Persistent shared state ───────────────────────────────────────────────────
if "shared" not in st.session_state:
    st.session_state.shared = {
        "lock": threading.Lock(),
        # What the camera sees RIGHT NOW (updates every frame)
        "live_colors": [(128, 128, 128)],
        # What the wallpaper is currently showing (only updates after stable period)
        "wall_colors": [(128, 128, 128)],
        # Debounce tracking
        "candidate_colors": [(128, 128, 128)],
        "candidate_since": 0.0,
        "stable_seconds": 4.0,   # seconds color must stay stable before switching
        "progress": 0.0,          # 0.0–1.0 progress toward commit
        "ready_to_commit": False,
    }

if "palette"  not in st.session_state: st.session_state.palette  = []
if "frozen"   not in st.session_state: st.session_state.frozen   = False
if "mode"     not in st.session_state: st.session_state.mode     = "Auto"

shared = st.session_state.shared

# ── Color math ────────────────────────────────────────────────────────────────
def extract_colors(frame_rgb: np.ndarray, n=6):
    """Accurate dominant color extraction using fine-grained bucketing."""
    h, w = frame_rgb.shape[:2]
    # Sample evenly across the whole frame
    small = frame_rgb[::max(1,h//50), ::max(1,w//50)].reshape(-1,3).astype(np.float32)

    # Fine buckets (32 shades per channel = 32768 buckets)
    buckets = {}
    for px in small:
        key = (int(px[0])>>3, int(px[1])>>3, int(px[2])>>3)
        if key not in buckets: buckets[key] = [0.0,0.0,0.0,0]
        buckets[key][0]+=px[0]; buckets[key][1]+=px[1]
        buckets[key][2]+=px[2]; buckets[key][3]+=1

    sorted_b = sorted(buckets.values(), key=lambda x: -x[3])

    colors = []
    for b in sorted_b:
        if b[3] == 0: continue
        r,g,bv = int(b[0]/b[3]), int(b[1]/b[3]), int(b[2]/b[3])
        # Must differ by >55 total from each already-accepted color
        if all(abs(r-c[0])+abs(g-c[1])+abs(bv-c[2]) > 55 for c in colors):
            colors.append((r, g, bv))
        if len(colors) >= n: break

    return colors if colors else [(128, 128, 128)]

def colors_similar(a, b, threshold=45):
    """True if two color lists represent roughly the same scene."""
    if not a or not b: return False
    # Compare primary colors
    r1,g1,b1 = a[0]; r2,g2,b2 = b[0]
    return abs(r1-r2)+abs(g1-g2)+abs(b1-b2) < threshold

def colors_are_distinct(colors, threshold=75):
    if len(colors) < 2: return False
    for i in range(len(colors)):
        for j in range(i+1, len(colors)):
            if sum(abs(colors[i][k]-colors[j][k]) for k in range(3)) > threshold:
                return True
    return False

def color_name_rgb(r, g, b):
    h,l,s = rgb_to_hls(r/255, g/255, b/255)
    if s < 0.10:
        return "Black" if l<.15 else ("White" if l>.85 else "Gray")
    if l < 0.08: return "Midnight"
    if l > 0.94: return "White"
    hd = int(h * 360)
    for lo,hi,name in [
        (0,8,"Red"),(8,18,"Deep Red"),(18,28,"Red-Orange"),
        (28,38,"Orange"),(38,48,"Amber"),(48,58,"Yellow-Orange"),
        (58,68,"Yellow"),(68,80,"Yellow-Green"),(80,105,"Chartreuse"),
        (105,140,"Green"),(140,160,"Emerald"),(160,175,"Teal"),
        (175,192,"Cyan-Teal"),(192,205,"Cyan"),(205,220,"Sky Blue"),
        (220,235,"Blue"),(235,248,"Deep Blue"),(248,258,"Cobalt"),
        (258,268,"Indigo"),(268,280,"Blue-Violet"),(280,295,"Violet"),
        (295,310,"Purple"),(310,325,"Magenta"),(325,340,"Pink"),
        (340,352,"Hot Pink"),(352,361,"Red"),
    ]:
        if lo <= hd < hi: return name
    return "Color"

def hls_c(h, l, s):
    h = h % 1.0
    l = max(0.0, min(1.0, l))
    s = max(0.0, min(1.0, s))
    return tuple(max(0, min(255, int(c*255))) for c in hls_to_rgb(h, l, s))

# ── Wallpaper renderers ───────────────────────────────────────────────────────
WW, WH = 1080, 1920

def radial(cx, cy, r, color, alpha=200):
    layer = Image.new("RGBA", (WW,WH), (0,0,0,0))
    d = ImageDraw.Draw(layer)
    steps = max(1, r//4)
    for i in range(steps, 0, -1):
        a  = int(alpha * (i/steps) ** 1.15)
        r2 = int(r * i/steps)
        d.ellipse([cx-r2,cy-r2,cx+r2,cy+r2], fill=(*color, a))
    return layer

def render_single(colors):
    r,g,b = colors[0]
    h,l,s = rgb_to_hls(r/255, g/255, b/255)
    s = min(1.0, s*1.6 + 0.25)
    l_mid = min(0.55, max(0.28, l))

    img = Image.new("RGBA", (WW,WH), (*hls_c(h, max(0.03, l_mid-0.26), s), 255))
    # Big central glow — the colour itself, very vivid
    img = Image.alpha_composite(img, radial(WW//2, WH//2,    int(WW*1.1),  hls_c(h, min(.78,l_mid+.26), s), 220))
    # Top-left accent
    img = Image.alpha_composite(img, radial(int(WW*.28), int(WH*.14), int(WW*.78), hls_c((h+.04)%1, min(.88,l_mid+.38), s), 185))
    # Bottom-right accent
    img = Image.alpha_composite(img, radial(int(WW*.74), int(WH*.86), int(WW*.78), hls_c((h-.04)%1, max(.08,l_mid-.14), min(1,s*1.1)), 185))
    # White shimmer
    img = Image.alpha_composite(img, radial(WW//2, int(WH*.38), int(WW*.32), (255,255,255), 38))
    return img.convert("RGB")

def render_aurora_multi(colors):
    cols = colors[:6]
    n    = len(cols)

    r0,g0,b0 = cols[0]
    h0,l0,s0 = rgb_to_hls(r0/255, g0/255, b0/255)
    img = Image.new("RGBA", (WW,WH), (*hls_c(h0, max(0.02, l0*.18), min(s0*.65,.6)), 255))

    zone_h = WH // n

    for i,(r,g,b) in enumerate(cols):
        h,l,s = rgb_to_hls(r/255, g/255, b/255)
        s      = min(1.0, s*1.7 + 0.32)
        l_vivid = min(0.74, max(0.33, l+0.22))
        yc     = int(zone_h*i + zone_h*.5)
        c_vivid = hls_c(h, l_vivid, s)

        # Full-width horizontal band
        band = Image.new("RGBA", (WW, WH), (0,0,0,0))
        bd   = ImageDraw.Draw(band)
        bh   = int(zone_h * .9)
        for row in range(WH):
            dist = abs(row - yc)
            if dist < bh*1.7:
                a = int(240 * max(0, 1-(dist/(bh*1.7))**.6))
                bd.line([(0,row),(WW,row)], fill=(*c_vivid, a))
        img = Image.alpha_composite(img, band)

        # Per-color blob
        xc = int(WW*(.18 + .64*((i+.5)/n)))
        c_bright = hls_c(h, min(.92, l_vivid+.2), s)
        img = Image.alpha_composite(img, radial(xc, yc, int(WW*.58), c_bright, 170))

    # Blend transitions between zones
    for i,(r,g,b) in enumerate(cols[:-1]):
        r2,g2,b2 = cols[i+1]
        bh2 = (r+r2)//2; bgh=(g+g2)//2; bbh=(b+b2)//2
        bhl,bll,bsl = rgb_to_hls(bh2/255, bgh/255, bbh/255)
        bsl = min(1.0, bsl*1.8+0.38)
        img = Image.alpha_composite(img, radial(WW//2, int(zone_h*(i+1)), int(WW*.44),
                                                hls_c(bhl, min(.82,bll+.34), bsl), 130))

    # Stars
    star = Image.new("RGBA", (WW,WH), (0,0,0,0))
    sd   = ImageDraw.Draw(star)
    rng  = random.Random(77)
    for _ in range(220):
        sx=int(rng.random()*WW); sy=int(rng.random()*WH)
        sr=rng.random()*2.0+.2
        sd.ellipse([sx-sr,sy-sr,sx+sr,sy+sr],
                   fill=(255,255,255,int(rng.random()*80+20)))
    img = Image.alpha_composite(img, star)

    # Smooth gaussian blend
    blurred = img.filter(ImageFilter.GaussianBlur(radius=22))
    return Image.blend(img.convert("RGB"), blurred.convert("RGB"), .32)

def render_wallpaper(colors, force_mode="Auto"):
    multi    = colors_are_distinct(colors)
    use_aurora = (force_mode=="Aurora") or (force_mode=="Auto" and multi and len(colors)>=2)
    if use_aurora: return render_aurora_multi(colors), True
    return render_single(colors), False

def img_bytes(img):
    buf = io.BytesIO(); img.save(buf, format="PNG"); return buf.getvalue()

# ── WebRTC callback — debounce logic lives HERE in the thread ─────────────────
def video_frame_callback(frame: av.VideoFrame) -> av.VideoFrame:
    if st.session_state.get("frozen", False):
        return frame

    arr  = frame.to_ndarray(format="rgb24")
    cols = extract_colors(arr, n=6)
    now  = time.time()

    with shared["lock"]:
        candidate = shared["candidate_colors"]
        stable_s  = shared["stable_seconds"]

        if colors_similar(cols, candidate, threshold=45):
            # Same color — accumulate time
            elapsed  = now - shared["candidate_since"]
            progress = min(1.0, elapsed / stable_s)
            shared["progress"] = progress
            shared["live_colors"] = cols

            if elapsed >= stable_s and not shared["ready_to_commit"]:
                # Stable long enough — commit to wallpaper
                shared["wall_colors"]      = cols
                shared["ready_to_commit"]  = True
        else:
            # Color changed — reset debounce
            shared["candidate_colors"]  = cols
            shared["candidate_since"]   = now
            shared["live_colors"]       = cols
            shared["progress"]          = 0.0
            shared["ready_to_commit"]   = False

    return frame

# ── UI ────────────────────────────────────────────────────────────────────────
st.markdown("""
<div style='text-align:center;padding:16px 0 4px;'>
  <span style='font-size:2rem;'>🦎</span>
  <div style='font-size:1.4rem;font-weight:600;color:#fff;margin:4px 0 2px;'>Chameleon Wallpaper</div>
  <div style='font-size:.75rem;color:rgba(255,255,255,.28);'>Holds color for 4s before switching • multi-color aurora</div>
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
    stab = st.selectbox("Hold time", ["3 seconds","4 seconds","5 seconds"])
    shared["stable_seconds"] = {"3 seconds":3.0,"4 seconds":4.0,"5 seconds":5.0}[stab]

SZ = {"1080×1920":(1080,1920),"1440×2560":(1440,2560),"1170×2532 (iPhone)":(1170,2532)}

col_freeze, _ = st.columns([1,2])
with col_freeze:
    if st.button("❄ Unfreeze" if st.session_state.frozen else "❄ Freeze", use_container_width=True):
        st.session_state.frozen = not st.session_state.frozen
        st.rerun()

hero_sl = st.empty(); pal_sl = st.empty(); wall_sl = st.empty(); dl_sl = st.empty()

def render_ui(wall_colors, live_colors, progress, ready):
    r,g,b   = wall_colors[0]
    lr,lg,lb = live_colors[0]
    hex_v   = f"#{r:02X}{g:02X}{b:02X}"
    live_hex = f"#{lr:02X}{lg:02X}{lb:02X}"
    cnames  = [color_name_rgb(*c) for c in wall_colors[:3]]
    live_name = color_name_rgb(lr,lg,lb)
    multi   = colors_are_distinct(wall_colors)
    fb      = " ❄" if st.session_state.frozen else ""

    swatches = "".join(
        f"<div class='swatch-circle' style='background:rgb{c};width:{'66' if i==0 else '46'}px;height:{'66' if i==0 else '46'}px;'></div>"
        for i,c in enumerate(wall_colors[:4])
    )

    # Status indicator
    if st.session_state.frozen:
        badge_dot = "dot-yellow"; badge_txt = "FROZEN"
        status_txt = f"Showing {hex_v}"
        prog_pct = 100
    elif not is_live:
        badge_dot = "dot-red"; badge_txt = "CAMERA OFF"
        status_txt = "Start camera to begin"
        prog_pct = 0
    elif ready or progress >= 1.0:
        badge_dot = "dot-green"; badge_txt = "LOCKED"
        status_txt = f"Wallpaper set to {color_name_rgb(lr,lg,lb)}"
        prog_pct = 100
    else:
        badge_dot = "dot-yellow"; badge_txt = "SCANNING"
        status_txt = f"Detecting {live_name} ({live_hex}) — holding {int(progress*shared['stable_seconds'])}s / {int(shared['stable_seconds'])}s"
        prog_pct = int(progress * 100)

    mode_info = f"<div class='multi-label'>🌈 {len(wall_colors)} colors → Aurora</div>" if multi else ""
    dark_bg = f"rgb({max(0,int(r*.12))},{max(0,int(g*.12))},{max(0,int(b*.12))})"

    hero_sl.markdown(f"""
<div class="hero" style="background:{dark_bg};">
  <div class="live-badge"><span class="dot {badge_dot}"></span>{badge_txt}</div>
  <div class="swatch-row">{swatches}</div>
  <p class="hex-txt">{hex_v}{fb}</p>
  <p class="name-txt">{' · '.join(cnames)}</p>
  {mode_info}
  <div class="progress-wrap"><div class="progress-fill" style="width:{prog_pct}%;"></div></div>
  <p class="status-txt">{status_txt}</p>
</div>""", unsafe_allow_html=True)

    pal = st.session_state.palette
    if pal:
        dots = "".join(f"<span class='pal-dot' style='background:{c};'></span>" for c in pal)
        pal_sl.markdown(f"<div class='card'><div class='sec-label'>Color history</div><div class='palette-row'>{dots}</div></div>",
                        unsafe_allow_html=True)

    wall_img, used_aurora = render_wallpaper(wall_colors, force_mode=st.session_state.mode)
    preview = wall_img.resize((360,640), Image.LANCZOS)
    wall_sl.image(preview, use_container_width=True,
                  caption=f"{'Aurora' if used_aurora else 'Gradient'}  •  {hex_v}  •  {' + '.join(cnames[:2])}")

    tw,th = SZ[sz]
    full = wall_img.resize((tw,th), Image.LANCZOS)
    dl_sl.download_button(
        label=f"⬇  Download  ({sz})",
        data=img_bytes(full),
        file_name=f"chameleon_{hex_v.strip('#')}_{'aurora' if used_aurora else 'gradient'}.png",
        mime="image/png",
        use_container_width=True,
    )

# ── Main loop ─────────────────────────────────────────────────────────────────
with shared["lock"]:
    wall_colors = list(tuple(c) for c in shared["wall_colors"])
    live_colors = list(tuple(c) for c in shared["live_colors"])
    progress    = shared["progress"]
    ready       = shared["ready_to_commit"]

if is_live:
    # Update palette when wallpaper commits
    if ready:
        hex_v = f"#{wall_colors[0][0]:02X}{wall_colors[0][1]:02X}{wall_colors[0][2]:02X}"
        if not st.session_state.palette or st.session_state.palette[0] != hex_v:
            st.session_state.palette.insert(0, hex_v)
            st.session_state.palette = st.session_state.palette[:8]

    render_ui(wall_colors, live_colors, progress, ready)
    time.sleep(0.5)   # refresh every 0.5s to update progress bar
    st.rerun()
else:
    render_ui(wall_colors, live_colors, 0.0, False)
    st.markdown("""<div style='text-align:center;padding:10px;color:rgba(255,255,255,.28);font-size:.78rem;'>
      ☝️ Click <b style='color:rgba(255,255,255,.6)'>START</b> above to activate live camera
    </div>""", unsafe_allow_html=True)

st.markdown("<div style='text-align:center;padding:16px 0 4px;color:rgba(255,255,255,.1);font-size:.62rem;'>🦎 Chameleon Wallpaper</div>",
            unsafe_allow_html=True)
