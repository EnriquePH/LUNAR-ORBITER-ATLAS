#!/usr/bin/env bash
# Render orbiter/assets/logo.svg into the favicon and PNG icons.
#
# Needs a Chromium-based browser (set CHROMIUM to override) and Pillow from .venv.
# Outputs: orbiter/assets/favicon.ico (16–64 px), icon-192.png, apple-touch-icon.png
# and the same icons for the GitHub Pages site in site/assets/.
set -euo pipefail

cd "$(dirname "$0")/.."
chromium=${CHROMIUM:-$(command -v chromium-browser || command -v chromium || command -v google-chrome)}
render=outputs/logo-512.png
mkdir -p outputs

# Snap-packaged Chromium cannot write to /tmp, so render inside the project.
"$chromium" --headless --disable-gpu --hide-scrollbars \
    --default-background-color=00000000 --window-size=512,512 \
    --screenshot="$PWD/$render" "file://$PWD/orbiter/assets/logo.svg" >/dev/null 2>&1

.venv/bin/python - "$render" <<'EOF'
import shutil
import sys
from pathlib import Path

from PIL import Image

logo = Image.open(sys.argv[1]).convert("RGBA")
assets = Path("orbiter/assets")
logo.save(assets / "favicon.ico", sizes=[(16, 16), (32, 32), (48, 48), (64, 64)])
for name, size in (("icon-192.png", 192), ("apple-touch-icon.png", 180)):
    logo.resize((size, size), Image.Resampling.LANCZOS).save(assets / name)

site = Path("site/assets")
site.mkdir(parents=True, exist_ok=True)
for name in ("logo.svg", "favicon.ico", "icon-192.png", "apple-touch-icon.png"):
    shutil.copy(assets / name, site / name)
print("Icons written to orbiter/assets and site/assets")
EOF
