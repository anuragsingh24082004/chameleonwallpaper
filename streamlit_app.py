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
.multi-label{font-size:.7rem;color:rgba(255,255,255,.5);background:rgba(255,255,255,.08);border-radius:8px;padding:3px 10px;display:inline-block;margin-top:6px;}
@keyframes blink{0%,100%{opacity:1}50%{opacity:.35}}
.stButton>button{font-family:'DM Sans',sans-serif!important;border-radius:14px!important;font-weight:500!important;border:1px solid rgba(255,255,255,.15)!important;background:rgba(255,255,255,.07)!important;color:rgba(255,255,255,.85)!important;width:100%!important;}
.stButton>button:hover{background:rgba(255,255,255,.14)!important;}
.stDownloadButton>button{border-radius:14px!important;font-weight:600!important;background:#22c55e!important;color:#000!important;border:none!important;width:100%!important;}
div[data-testid="stSelectbox"]>div>div{background:rgba(255,255,255,.07)!important;border:1px solid rgba(255,255,255,.12)!important;border-radius:12px!important;color:#fff!important;}
label{color:rgba(255,255,255,.4)!important;font-size:.72rem!important;text-transform:uppercase!important;letter-spacing:1px!important;}
</style>
""", unsafe_allow_html=True)

# ── Persistent shared state — survives st.rerun() ────────────────────────────
# Store a mutable dict in session_state so the WebRTC thread can write to it
# and the main thread reads from it WITHOUT it being reset on every rerun.
if "shared" not in st.session_state:
    st.session_state.shared = {
        "colors": [(30, 30, 80)],
        "lock": threading.Lock(),
    }
if "palette"  not in st.session_state: st.session_state.palette  = []
if "frozen"   not in st.session_state: st.session_state.frozen   = False
if "mode"     not in st.session_state: st.session_state.mode     = "Auto"

shared = st.session_state.shared   # shorthand

# ── Color extraction ──────────────────────────────────────────────────────────
def extract_colors(frame_rgb: np.ndarray, n=5):
    h, w = frame_rgb.shape[:2]
    small = frame_rgb[::max(1,h//40), ::max(1,w//40)].reshape(-1,3).astype(np.float32)
    buckets = {}
    for px in small:
        key = (int(px[0])>>5, int(px[1])>>5, int(px[2])>>5)
        if key not in buckets: buckets[key] = [0,0,0,0]
        buckets[key][0]+=px[0]; buckets[key][1]+=px[1]
        buckets[key][2]+=px[2]; buckets[key][3]+=1
    sorted_b = sorted(buckets.values(), key=lambda x: -x[3])
    colors = []
    for b in sorted_b:
        if b[3]==0: continue
        r,g,bv = int(b[0]/b[3]),int(b[1]/b[3]),int(b[2]/b[3])
        if all(abs(r-c[0])+abs(g-c[1])+abs(bv-c[2])>60 for c in colors):
            colors.append((r,g,bv))
        if len(colors)>=n: break
    return colors if colors else [(128,128,128)]

def colors_are_distinct(colors, threshold=80):
    if len(colors)<2: return False
    for i in range(len(colors)):
        for j in range(i+1,len(colors)):
            if sum(abs(colors[i][k]-colors[j][k]) for k in range(3))>threshold:
                return True
    return False

def color_name_rgb(r,g,b):
    h,l,s = rgb_to_hls(r/255,g/255,b/255)
    if s<0.12: return "Deep Black" if l<.2 else ("Pure White" if l>.8 else "Neutral Gray")
    if l<0.1: return "Midnight"
    hd=int(h*360)
    for lo,hi,n in [(0,15,"Crimson Red"),(15,30,"Sunset Orange"),(30,45,"Amber Glow"),
                    (45,65,"Golden Yellow"),(65,80,"Lime Green"),(80,150,"Forest Green"),
                    (150,175,"Emerald Teal"),(175,200,"Aqua Cyan"),(200,230,"Ocean Blue"),
                    (230,260,"Deep Cobalt"),(260,280,"Royal Indigo"),(280,310,"Violet Purple"),
                    (310,340,"Magenta Rose"),(340,361,"Crimson Red")]:
        if lo<=hd<hi: return n
    return "Pure Hue"

def hls_c(h,l,s):
    return tuple(max(0,min(255,int(c*255))) for c in hls_to_rgb(h%1,
                 max(0.0,min(1.0,l)), max(0.0,min(1.0,s))))

# ── Renderers ─────────────────────────────────────────────────────────────────
WW, WH = 1080, 1920

def radial(cx,cy,r,color,alpha=200):
    layer=Image.new("RGBA",(WW,WH),(0,0,0,0))
    d=ImageDraw.Draw(layer)
    steps=max(1,r//4)
    for i in range(steps,0,-1):
        a=int(alpha*(i/steps)**1.2); r2=int(r*i/steps)
        d.ellipse([cx-r2,cy-r2,cx+r2,cy+r2],fill=(*color,a))
    return layer

def render_single(colors):
    r,g,b=colors[0]
    h,l,s=rgb_to_hls(r/255,g/255,b/255)
    s=min(1.0,s*1.5+0.25)
    l_mid=min(0.55,max(0.3,l))
    img=Image.new("RGBA",(WW,WH),(*hls_c(h,max(0.04,l_mid-0.25),s),255))
    img=Image.alpha_composite(img,radial(WW//2,WH//2,int(WW*1.1),hls_c(h,min(.75,l_mid+.25),s),215))
    img=Image.alpha_composite(img,radial(int(WW*.3),int(WH*.15),int(WW*.75),hls_c((h+.03)%1,min(.85,l_mid+.35),s),185))
    img=Image.alpha_composite(img,radial(int(WW*.72),int(WH*.85),int(WW*.75),hls_c((h-.03)%1,max(.1,l_mid-.12),min(1,s*1.1)),185))
    img=Image.alpha_composite(img,radial(WW//2,WH//2,int(WW*.35),(255,255,255),40))
    return img.convert("RGB")

def render_aurora_multi(colors):
    cols=colors[:5]; n=len(cols)
    r0,g0,b0=cols[0]
    h0,l0,s0=rgb_to_hls(r0/255,g0/255,b0/255)
    img=Image.new("RGBA",(WW,WH),(*hls_c(h0,max(0.03,l0*.2),min(s0*.7,.65)),255))
    zone_h=WH//n
    for i,(r,g,b) in enumerate(cols):
        h,l,s=rgb_to_hls(r/255,g/255,b/255)
        s=min(1.0,s*1.6+0.3); l_vivid=min(0.72,max(0.35,l+0.2))
        yc=int(zone_h*i+zone_h*.5)
        c_vivid=hls_c(h,l_vivid,s)
        band=Image.new("RGBA",(WW,WH),(0,0,0,0)); bd=ImageDraw.Draw(band)
        bh=int(zone_h*.85)
        for row in range(WH):
            dist=abs(row-yc)
            if dist<bh*1.6:
                a=int(235*max(0,1-(dist/(bh*1.6))**.65))
                bd.line([(0,row),(WW,row)],fill=(*c_vivid,a))
        img=Image.alpha_composite(img,band)
        xc=int(WW*(.2+.6*((i+.5)/n)))
        img=Image.alpha_composite(img,radial(xc,yc,int(WW*.55),hls_c(h,min(.9,l_vivid+.18),s),165))
    for i,(r,g,b) in enumerate(cols[:-1]):
        r2,g2,b2=cols[i+1]
        bh2=(r+r2)//2; bgh=(g+g2)//2; bbh=(b+b2)//2
        bhl,bll,bsl=rgb_to_hls(bh2/255,bgh/255,bbh/255)
        bsl=min(1.0,bsl*1.7+0.35)
        img=Image.alpha_composite(img,radial(WW//2,int(zone_h*(i+1)),int(WW*.42),hls_c(bhl,min(.8,bll+.32),bsl),125))
    star=Image.new("RGBA",(WW,WH),(0,0,0,0)); sd=ImageDraw.Draw(star)
    rng=random.Random(99)
    for _ in range(200):
        sx=int(rng.random()*WW); sy=int(rng.random()*WH)
        sr=rng.random()*1.8+.2
        sd.ellipse([sx-sr,sy-sr,sx+sr,sy+sr],fill=(255,255,255,int(rng.random()*85+25)))
    img=Image.alpha_composite(img,star)
    blurred=img.filter(ImageFilter.GaussianBlur(radius=20))
    return Image.blend(img.convert("RGB"),blurred.convert("RGB"),.3)

def render_wallpaper(colors,force_mode="Auto"):
    multi=colors_are_distinct(colors)
    use_aurora=(force_mode=="Aurora") or (force_mode=="Auto" and multi and len(colors)>=2)
    if use_aurora: return render_aurora_multi(colors),True
    return render_single(colors),False

def img_bytes(img):
    buf=io.BytesIO(); img.save(buf,format="PNG"); return buf.getvalue()

# ── WebRTC callback — writes into session_state.shared (persists across reruns)
def video_frame_callback(frame: av.VideoFrame) -> av.VideoFrame:
    if not st.session_state.get("frozen", False):
        arr=frame.to_ndarray(format="rgb24")
        cols=extract_colors(arr,n=5)
        with shared["lock"]:
            shared["colors"]=cols   # ← mutable dict update, NOT reassignment
    return frame

# ── Header ────────────────────────────────────────────────────────────────────
st.markdown("""
<div style='text-align:center;padding:16px 0 4px;'>
  <span style='font-size:2rem;'>🦎</span>
  <div style='font-size:1.4rem;font-weight:600;color:#fff;margin:4px 0 2px;'>Chameleon Wallpaper</div>
  <div style='font-size:.75rem;color:rgba(255,255,255,.28);'>Real-time camera → full-color wallpaper</div>
</div>
""", unsafe_allow_html=True)

ctx=webrtc_streamer(
    key="chameleon",
    mode=WebRtcMode.SENDONLY,
    video_frame_callback=video_frame_callback,
    rtc_configuration=RTCConfiguration({"iceServers":[{"urls":["stun:stun.l.google.com:19302"]}]}),
    media_stream_constraints={"video":{"width":320,"height":240},"audio":False},
    async_processing=True,
)
is_live=ctx.state.playing if ctx else False

c1,c2,c3=st.columns(3)
with c1:
    mode=st.selectbox("Style",["Auto","Aurora","Gradient"])
    st.session_state.mode=mode
with c2:
    sz=st.selectbox("Size",["1080×1920","1440×2560","1170×2532 (iPhone)"])
with c3:
    if st.button("❄ Unfreeze" if st.session_state.frozen else "❄ Freeze",use_container_width=True):
        st.session_state.frozen=not st.session_state.frozen
        st.rerun()

SZ={"1080×1920":(1080,1920),"1440×2560":(1440,2560),"1170×2532 (iPhone)":(1170,2532)}

hero_sl=st.empty(); pal_sl=st.empty(); wall_sl=st.empty(); dl_sl=st.empty()

def render_ui(colors):
    r,g,b=colors[0]
    hex_v=f"#{r:02X}{g:02X}{b:02X}"
    cnames=[color_name_rgb(*c) for c in colors[:3]]
    multi=colors_are_distinct(colors)
    fb=" ❄" if st.session_state.frozen else ""
    swatches="".join(
        f"<div class='swatch-circle' style='background:rgb{c};width:{'66' if i==0 else '46'}px;height:{'66' if i==0 else '46'}px;'></div>"
        for i,c in enumerate(colors[:4])
    )
    mode_info=f"<div class='multi-label'>🌈 {len(colors)} colors → Aurora</div>" if multi else ""
    dark_bg=f"rgb({max(0,int(r*.12))},{max(0,int(g*.12))},{max(0,int(b*.12))})"
    hero_sl.markdown(f"""
<div class="hero" style="background:{dark_bg};">
  <div class="live-badge"><span class="dot {'dot-green' if is_live else 'dot-red'}"></span>{'LIVE' if is_live else 'CAMERA OFF'}</div>
  <div class="swatch-row">{swatches}</div>
  <p class="hex-txt">{hex_v}{fb}</p>
  <p class="name-txt">{' · '.join(cnames)}</p>
  {mode_info}
</div>""",unsafe_allow_html=True)

    pal=st.session_state.palette
    if pal:
        dots="".join(f"<span class='pal-dot' style='background:{c};'></span>" for c in pal)
        pal_sl.markdown(f"<div class='card'><div class='sec-label'>Color history</div><div class='palette-row'>{dots}</div></div>",unsafe_allow_html=True)

    wall_img,used_aurora=render_wallpaper(colors,force_mode=st.session_state.mode)
    preview=wall_img.resize((360,640),Image.LANCZOS)
    wall_sl.image(preview,use_container_width=True,
                  caption=f"{'Aurora' if used_aurora else 'Gradient'}  •  {hex_v}  •  {' + '.join(cnames[:2])}")
    tw,th=SZ[sz]
    full=wall_img.resize((tw,th),Image.LANCZOS)
    dl_sl.download_button(
        label=f"⬇  Download  ({sz})",
        data=img_bytes(full),
        file_name=f"chameleon_{hex_v.strip('#')}_{'aurora' if used_aurora else 'gradient'}.png",
        mime="image/png",
        use_container_width=True,
    )

# ── Main loop ─────────────────────────────────────────────────────────────────
if is_live:
    with shared["lock"]:
        colors=list(tuple(c) for c in shared["colors"])  # read fresh colors

    hex_v=f"#{colors[0][0]:02X}{colors[0][1]:02X}{colors[0][2]:02X}"
    if not st.session_state.palette or st.session_state.palette[0]!=hex_v:
        st.session_state.palette.insert(0,hex_v)
        st.session_state.palette=st.session_state.palette[:8]

    render_ui(colors)
    time.sleep(0.8)
    st.rerun()
else:
    with shared["lock"]:
        colors=list(tuple(c) for c in shared["colors"])
    render_ui(colors)
    st.markdown("""<div style='text-align:center;padding:10px;color:rgba(255,255,255,.28);font-size:.78rem;'>
      ☝️ Click <b style='color:rgba(255,255,255,.6)'>START</b> above to go live
    </div>""",unsafe_allow_html=True)

st.markdown("<div style='text-align:center;padding:16px 0 4px;color:rgba(255,255,255,.1);font-size:.62rem;'>🦎 Chameleon Wallpaper</div>",unsafe_allow_html=True)
