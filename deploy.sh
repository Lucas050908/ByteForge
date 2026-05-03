#!/usr/bin/env bash
# ByteForge quick deploy — copies latest files to /opt/byteforge and restarts the service
set -euo pipefail

SRC="$(cd "$(dirname "${BASH_SOURCE[0]}")/ByteForge" && pwd)"
DEST="/opt/byteforge"

echo "Deploying ByteForge..."
sudo cp "$SRC/byteforge-server.py"       "$DEST/byteforge-server.py"
sudo cp "$SRC/byteforge-platform.html"   "$DEST/byteforge-platform.html"
sudo cp "$SRC/byteforge-platform.js"     "$DEST/byteforge-platform.js"
sudo cp "$SRC/byteforge-platform.css"    "$DEST/byteforge-platform.css"
sudo systemctl restart byteforge
echo "Done. Running at http://localhost:8080"
