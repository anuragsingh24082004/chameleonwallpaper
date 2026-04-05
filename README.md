# 🦎 Chameleon Wallpaper

> A real Android app written in **Python + Kivy** that uses your phone camera 24/7 to detect surrounding colors and changes your wallpaper in real-time — just like a chameleon.

---

## How It Works

```
Camera Frame  →  Extract Dominant Color  →  Render Wallpaper Bitmap  →  WallpaperManager.setBitmap()
   (320×240)        (pixel average)           (Solid / Gradient / Aurora)    (Home + Lock screen)
```

Every ~300ms the app:
1. Samples a live camera frame
2. Averages pixel colors across a grid to find the dominant hue
3. Renders a styled wallpaper bitmap (Solid, Gradient, or Aurora mode)
4. Sets **both home screen and lock screen** wallpapers using Android's `WallpaperManager`

---

## Features

| Feature | Details |
|---|---|
| 🎨 Live color detection | Camera sampled every 300ms, dominant color extracted |
| 🖼️ 3 Wallpaper styles | Solid · Gradient (ambient blobs) · Aurora (bands + stars) |
| ❄️ Freeze | Lock current detected color indefinitely |
| 🔄 Camera flip | Toggle between front and rear camera |
| ⚡ Speed control | Instant / Fast / Normal / Slow / Dreamy (5 levels) |
| 🎨 Color history | Last 7 detected colors shown as live swatches |
| 🌙 Home + Lock | Sets both wallpapers simultaneously |

---

## Tech Stack

| Layer | Technology |
|---|---|
| Language | Python 3.11 |
| UI Framework | [Kivy 2.3](https://kivy.org) |
| Android bridge | [Pyjnius](https://pyjnius.readthedocs.io) |
| Camera | Kivy Camera widget + CameraX (via Pyjnius) |
| Wallpaper API | `android.app.WallpaperManager` via Pyjnius |
| APK builder | [Buildozer](https://buildozer.readthedocs.io) |
| CI/CD | GitHub Actions (auto-builds APK on push) |

---

## 🚀 Get the APK (No setup required)

1. Go to the **Actions** tab on GitHub
2. Click the latest **"Build Android APK"** run
3. Download the **`chameleon-wallpaper-debug-apk`** artifact
4. Install the APK on your Android phone (enable "Install unknown apps" in settings)

---

## Build Locally

### Prerequisites

- Python 3.10 or 3.11
- Linux or macOS (Windows: use WSL2)
- Java 17 (`sudo apt install openjdk-17-jdk`)

### Steps

```bash
# 1. Clone the repo
git clone https://github.com/YOUR_USERNAME/chameleon-wallpaper.git
cd chameleon-wallpaper

# 2. Create a virtual environment
python3 -m venv venv
source venv/bin/activate

# 3. Install buildozer
pip install buildozer cython==0.29.36

# 4. Build the debug APK (first build takes ~20 min — downloads Android SDK/NDK)
buildozer android debug

# 5. The APK will be in ./bin/
ls bin/*.apk
```

### Deploy directly to phone via USB

```bash
# Connect your Android phone with USB debugging enabled, then:
buildozer android deploy run logcat
```

---

## Project Structure

```
chameleon-wallpaper/
├── main.py                   ← App entry point: UI + color engine + wallpaper logic
├── buildozer.spec            ← Android build config (permissions, SDK version, etc.)
├── requirements.txt          ← Python dependencies
├── .gitignore
├── README.md
└── .github/
    └── workflows/
        └── build.yml         ← GitHub Actions: auto-build APK on every push
```

---

## Permissions

| Permission | Why needed |
|---|---|
| `CAMERA` | Read live frames for color detection |
| `SET_WALLPAPER` | Apply generated wallpaper to home/lock screen |
| `FOREGROUND_SERVICE` | Run continuously in background |
| `FOREGROUND_SERVICE_CAMERA` | Android 14+ requirement for camera in services |
| `POST_NOTIFICATIONS` | Show status notification while running |

---

## Upload to GitHub (New Repo)

```bash
cd chameleon-wallpaper-python
git init
git add .
git commit -m "feat: initial Chameleon Wallpaper Python app"
git branch -M main
git remote add origin https://github.com/YOUR_USERNAME/chameleon-wallpaper.git
git push -u origin main
```

After pushing, GitHub Actions automatically starts building your APK. Check the **Actions** tab.

---

## Requirements

- Android **8.0+** (API 26)
- Any Android phone with a camera
- ~80MB storage for the APK + runtime

---

## License

MIT — free to use, modify, and distribute.
