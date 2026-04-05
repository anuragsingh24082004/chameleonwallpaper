"""
🦎 Chameleon Wallpaper — Real-time Streamlit App
Uses streamlit-webrtc for continuous live camera feed.
Run: streamlit run streamlit_app.py
"""

import io
import threading
import time
import random
from colorsys import rgb_to_hls, hls_to_rgb

import av
import numpy as np
import streamlit as st
from PIL import Image, ImageDraw
from streamlit_webrtc import webrtc_streamer, WebRtcMode, RTCConfiguration

st.set_page_config(
    page_title="Chameleon Wallpaper",
    page_icon="🦎",
    layout="centered",
    initial_sidebar_state="collapsed",
)

st.markdown("""
<style>
@import url('https://fonts.googleapis.com/css2?family=DM+Sans:wght@300;400;600&family=DM+Mono:wght@400&display=swap');
html,body,[data-testid="stAppViewContainer"]{font-family:'DM Sans',sans-serif;background:#0d0d1a!important;}
[data-testid="stHeader"]{background:transparent!important;}
[data-testid="stMainBlockContainer"]{padding-top:1rem!important;}
footer,#MainMenu{display:none!important;}
.hero{border-radius:24px;padding:28px 20px 22px;margin-bottom:16px;text-align:center;}
.swatch{width:110px;height:110px;border-radius:50%;margin:0 auto 14px;border:2.5px solid rgba(255,255,255,0.18);}
.hex-txt{font-family:'DM Mono',monospace;font-size:2rem;color:#fff;letter-spacing:3px;margin:0;}
.name-txt{font-size:.82rem;color:rgba(255,255,255,.45);margin:6px 0 0;letter-spacing:.5px;}
.bri-bar{background:rgba(255,255,255,.1);border-radius:4px;height:4px;margin:12px auto 4px;max-width:220px;overflow:hidden;}
.bri-fill{height:100%;border-radius:4px;}
.palette-row{display:flex;gap:9px;justify-content:center;flex-wrap:wrap;margin:14px 0 2px;}
.pal-dot{width:36px;height:36px;border-radius:11px;border:1px solid rgba(255,255,255,.12);display:inline-block;}
.card{background:rgba(255,255,255,.05);border:1px solid rgba(255,255,255,.08);border-radius:18px;padding:16px 18px;margin-bottom:12px;}
.sec-label{font-size:.68rem;font-weight:600;letter-spacing:1.5px;color:rgba(255,255,255,.3);text-transform:uppercase;margin-bottom:10px;}
.live-badge{display:inline-flex;align-items:center;gap:7px;background:rgba(0,0,0,.45);border:1px solid rgba(255,255,255,.1);border-radius:100px;padding:5px 14px;font-size:.7rem;font-weight:600;color:rgba(255,255,255,.8);letter-spacing:.8px;margin-bottom:18px;}
.dot{width:8px;height:8px;border-radius:50%;display:inline-block;}
.dot-green{background:#22c55e;animation:blink 1.8s infinite;}
.dot-red{background:#ef4444;}
@keyframes blink{0%,100%{opacity:1}50%{opacity:.35}}
.stButton>button{font-family:'DM Sans',sans-serif!important;border-radius:14px!important;font-weight:500!important;border:1px solid rgba(255,255,255,.15)!important;background:rgba(255,255,255,.07)!important;color:rgba(255,255,255,.85)!important;width:100%!important;}
.stButton>button:hover{background:rgba(255,255,255,.14)!important;border-color:rgba(255,255,255,.3)!important;}
.stDownloadButton>button{border-radius:14px!important;font-family:'DM Sans',sans-serif!important;font-weight:600!important;background:#22c55e!important;color:#000!important;border:none!important;width:100%!important;}
div[data-testid="stSelectbox"]>div>div{background:rgba(255,255,255,.07)!important;border:1px solid rgba(255,255,255,.12)!important;border-radius:12px!important;color:#fff!important;}
label{color:rgba(255,255,255,.4)!important;font-size:.72rem!important;text-transform:uppercase!important;letter-spacing:1px!important;}
</style>
""", unsafe_allow_html=True)

# ── Shared state ──────────────────────────────────────────────────────────────
if "dominant_rgb" not in st.session_state: st.session_state.dominant_rgb = (30, 30, 80)
if "palette"      not in st.session_state: st.session_state.palette      = []
if "frozen"       not in st.session_state: st.session_state.frozen       = False
if "mode"         not in st.session_state: st.session_state.mode         = "Gradient"

_lock      = threading.Lock()
_latest_rgb = [30, 30, 80]

# ── Color helpers ─────────────────────────────────────────────────────────────
def extract_dominant(frame_rgb: np.ndarray):
    s = frame_rgb[::max(1,frame_rgb.shape[0]//30), ::max(1,frame_rgb.shape[1]//30)]
    avg = s.reshape(-1,3).mean(axis=0)
    return int(avg[0]), int(avg[1]), int(avg[2])

def color_name(h, s, l):
    if s < 0.12:
        return "Deep Black" if l<.20 else ("Pure White" if l>.80 else "Neutral Gray")
    if l < 0.10: return "Midnight Dark"
    if l > 0.92: return "Bright White"
    hd = int(h*360)
    for lo,hi,n in [(0,15,"Crimson Red"),(15,30,"Sunset Orange"),(30,45,"Amber Glow"),
                    (45,65,"Golden Yellow"),(65,80,"Lime Chartreuse"),(80,150,"Forest Green"),
                    (150,175,"Emerald Teal"),(175,200,"Aqua Cyan"),(200,230,"Ocean Blue"),
                    (230,260,"Deep Cobalt"),(260,280,"Royal Indigo"),(280,310,"Violet Purple"),
                    (310,340,"Magenta Rose"),(340,361,"Crimson Red")]:
        if lo<=hd<hi: return n
    return "Pure Hue"

def hls_c(h,l,s): return tuple(int(c*255) for c in hls_to_rgb(h,l,s))

# ── Wallpaper renderers ───────────────────────────────────────────────────────
WW, WH = 1080, 1920

def radial_blob(cx, cy, radius, color_rgb, alpha=150):
    layer = Image.new("RGBA",(WW,WH),(0,0,0,0))
    d = ImageDraw.Draw(layer)
    steps = max(1,radius//6)
    for i in range(steps,0,-1):
        a = int(alpha*(i/steps)**1.4); r2=int(radius*i/steps)
        d.ellipse([cx-r2,cy-r2,cx+r2,cy+r2], fill=(*color_rgb,a))
    return layer

def render_gradient(r,g,b,h,l,s):
    dl=max(.03,l-.22); bg=hls_c(h,dl,min(s,.8))
    img=Image.new("RGB",(WW,WH),bg); ov=Image.new("RGBA",(WW,WH),(0,0,0,0))
    ov=Image.alpha_composite(ov,radial_blob(int(WW*.18),int(WH*.18),int(WW*.85),hls_c(h,min(.75,l+.22),s),155))
    ov=Image.alpha_composite(ov,radial_blob(int(WW*.82),int(WH*.76),int(WW*.72),hls_c((h+.08)%1,min(.65,l+.1),s),140))
    ov=Image.alpha_composite(ov,radial_blob(WW//2,int(WH*.34),int(WW*.48),(255,255,255),50))
    vig=Image.new("RGBA",(WW,WH),(0,0,0,0)); vd=ImageDraw.Draw(vig)
    cx,cy=WW//2,WH//2
    for i in range(max(WW,WH),0,-12):
        ratio=i/max(WW,WH)
        if ratio<.38: vd.ellipse([cx-i,cy-i,cx+i,cy+i],fill=(0,0,0,int(160*(.38-ratio)/.38)))
    return Image.alpha_composite(Image.alpha_composite(img.convert("RGBA"),ov),vig).convert("RGB")

def render_solid(r,g,b,h,l,s):
    img=Image.new("RGB",(WW,WH),hls_c(h,max(.03,l-.18),s))
    ov=Image.new("RGBA",(WW,WH),(0,0,0,0)); od=ImageDraw.Draw(ov)
    cx,cy=WW//2,WH//2
    for i in range(max(WW,WH),0,-10):
        od.ellipse([cx-i,cy-i,cx+i,cy+i],fill=(0,0,0,int(180*max(0,1-i/(max(WW,WH)*.62)))))
    return Image.alpha_composite(img.convert("RGBA"),ov).convert("RGB")

def render_aurora(r,g,b,h,l,s):
    img=Image.new("RGB",(WW,WH),hls_c(h,max(.03,l-.25),min(s,.7)))
    ov=Image.new("RGBA",(WW,WH),(0,0,0,0))
    for i,bh in enumerate([h,(h+.11)%1,(h+.25)%1,(h+.42)%1]):
        yp=int(WH*(.18+i*.19)); bht=int(WH*.23)
        bc=hls_c(bh,min(.72,l+.26),min(.95,s+.2))
        band=Image.new("RGBA",(WW,bht*2),(0,0,0,0)); bd=ImageDraw.Draw(band)
        for row in range(bht*2):
            bd.line([(0,row),(WW,row)],fill=(*bc,int(120*max(0,1-abs(row-bht)/bht))))
        ov.alpha_composite(band,(0,yp-bht))
    star=Image.new("RGBA",(WW,WH),(0,0,0,0)); sd=ImageDraw.Draw(star)
    rng=random.Random(42)
    for _ in range(150):
        sx=int(rng.random()*WW); sy=int(rng.random()*WH*.55); sr=rng.random()*1.5+.3
        sd.ellipse([sx-sr,sy-sr,sx+sr,sy+sr],fill=(255,255,255,int(rng.random()*110+55)))
    return Image.alpha_composite(Image.alpha_composite(img.convert("RGBA"),ov),star).convert("RGB")

RENDERERS={"Gradient":render_gradient,"Solid":render_solid,"Aurora":render_aurora}

def img_bytes(img):
    buf=io.BytesIO(); img.save(buf,format="PNG"); return buf.getvalue()

# ── WebRTC callback ───────────────────────────────────────────────────────────
def video_frame_callback(frame: av.VideoFrame) -> av.VideoFrame:
    if not st.session_state.get("frozen", False):
        arr = frame.to_ndarray(format="rgb24")
        r,g,b = extract_dominant(arr)
        with _lock:
            _latest_rgb[0]=r; _latest_rgb[1]=g; _latest_rgb[2]=b
    return frame

# ── Header ────────────────────────────────────────────────────────────────────
st.markdown("""
<div style='text-align:center;padding:20px 0 6px;'>
  <span style='font-size:2rem;'>🦎</span>
  <div style='font-size:1.45rem;font-weight:600;color:#fff;margin:4px 0 2px;'>Chameleon Wallpaper</div>
  <div style='font-size:.8rem;color:rgba(255,255,255,.35);'>Live camera → real-time color → wallpaper</div>
</div>
""", unsafe_allow_html=True)

# ── WebRTC streamer ───────────────────────────────────────────────────────────
ctx = webrtc_streamer(
    key="chameleon",
    mode=WebRtcMode.SENDONLY,
    video_frame_callback=video_frame_callback,
    rtc_configuration=RTCConfiguration(
        {"iceServers": [{"urls": ["stun:stun.l.google.com:19302"]}]}
    ),
    media_stream_constraints={"video": {"width":320,"height":240}, "audio": False},
    async_processing=True,
)
is_live = ctx.state.playing if ctx else False

# ── Controls ──────────────────────────────────────────────────────────────────
c1,c2,c3 = st.columns(3)
with c1:
    mode = st.selectbox("Style", ["Gradient","Solid","Aurora"])
    st.session_state.mode = mode
with c2:
    sz = st.selectbox("Size", ["1080×1920","1440×2560","1170×2532 (iPhone)"])
with c3:
    if st.button("❄ Unfreeze" if st.session_state.frozen else "❄ Freeze", use_container_width=True):
        st.session_state.frozen = not st.session_state.frozen
        st.rerun()

SZ={"1080×1920":(1080,1920),"1440×2560":(1440,2560),"1170×2532 (iPhone)":(1170,2532)}
WW,WH=SZ[sz]

# ── Live UI slots ─────────────────────────────────────────────────────────────
hero_sl    = st.empty()
pal_sl     = st.empty()
wall_sl    = st.empty()
dl_sl      = st.empty()

def render_ui(r, g, b):
    rf,gf,bf = r/255,g/255,b/255
    h,l,s    = rgb_to_hls(rf,gf,bf)
    hex_v    = f"#{r:02X}{g:02X}{b:02X}"
    cname    = color_name(h,s,l)
    bri      = int((0.299*r+0.587*g+0.114*b)/255*100)
    dark_bg  = f"rgb({max(0,int(r*.15))},{max(0,int(g*.15))},{max(0,int(b*.15))})"
    fb       = " ❄" if st.session_state.frozen else ""

    hero_sl.markdown(f"""
<div class="hero" style="background:linear-gradient(145deg,{dark_bg},{dark_bg});">
  <div class="live-badge">
    <span class="dot {'dot-green' if is_live else 'dot-red'}"></span>
    {'LIVE' if is_live else 'CAMERA OFF'}
  </div>
  <div class="swatch" style="background:rgb({r},{g},{b});"></div>
  <p class="hex-txt">{hex_v}{fb}</p>
  <p class="name-txt">{cname}</p>
  <div class="bri-bar"><div class="bri-fill" style="width:{bri}%;background:rgb({r},{g},{b});"></div></div>
  <p style="font-size:.65rem;color:rgba(255,255,255,.25);margin:4px 0 0;">Brightness {bri}%</p>
</div>""", unsafe_allow_html=True)

    pal = st.session_state.palette
    if pal:
        dots="".join(f"<span class='pal-dot' style='background:{c};'></span>" for c in pal)
        pal_sl.markdown(f"<div class='card'><div class='sec-label'>Color history</div><div class='palette-row'>{dots}</div></div>",
                        unsafe_allow_html=True)

    wall_img = RENDERERS[st.session_state.mode](r,g,b,h,l,s)
    preview  = wall_img.resize((360,640), Image.LANCZOS)
    wall_sl.image(preview, use_container_width=True, caption=f"{mode}  •  {hex_v}  •  {cname}")

    full = wall_img.resize(SZ[sz], Image.LANCZOS)
    dl_sl.download_button(
        label=f"⬇  Download Wallpaper  ({sz})",
        data=img_bytes(full),
        file_name=f"chameleon_{hex_v.strip('#')}_{mode.lower()}.png",
        mime="image/png",
        use_container_width=True,
    )

# ── Main loop ─────────────────────────────────────────────────────────────────
if is_live:
    with _lock:
        r,g,b = _latest_rgb[0],_latest_rgb[1],_latest_rgb[2]
    hex_v = f"#{r:02X}{g:02X}{b:02X}"
    if not st.session_state.palette or st.session_state.palette[0] != hex_v:
        st.session_state.palette.insert(0, hex_v)
        st.session_state.palette = st.session_state.palette[:8]
    st.session_state.dominant_rgb = (r,g,b)
    render_ui(r,g,b)
    time.sleep(1)
    st.rerun()
else:
    r,g,b = st.session_state.dominant_rgb
    render_ui(r,g,b)
    st.markdown("""<div style='text-align:center;padding:10px;color:rgba(255,255,255,.35);font-size:.8rem;'>
      ☝️ Click <b style='color:rgba(255,255,255,.7)'>START</b> on the camera widget above to go live
    </div>""", unsafe_allow_html=True)

st.markdown("<div style='text-align:center;padding:20px 0 6px;color:rgba(255,255,255,.15);font-size:.68rem;'>🦎 Chameleon Wallpaper</div>",
            unsafe_allow_html=True)
