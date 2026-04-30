#!/bin/bash
# ByteForge Theme Deploy Script
# Run med: sudo bash byteforge-deploy.sh

set -e
WWW="/var/lib/casaos/www"

echo -e "\e[38;5;208m[BYTEFORGE] Deploying theme...\e[0m"

# 1. Backup original custom.css
if [ ! -f "$WWW/css/custom.css.bak" ]; then
  cp "$WWW/css/custom.css" "$WWW/css/custom.css.bak"
  echo -e "\e[32m[  OK  ]\e[0m Backed up original custom.css"
fi

# 2. Copy ByteForge CSS
cp "$(dirname "$0")/byteforge-custom.css" "$WWW/css/custom.css"
echo -e "\e[32m[  OK  ]\e[0m ByteForge CSS deployed"

# 3. Inject CSS + favicon into index.html
if ! grep -q "byteforge" "$WWW/index.html"; then
  # Inject custom font + css link into <head>
  sed -i 's|</head>|<link rel="preconnect" href="https://fonts.googleapis.com"><link href="https://fonts.googleapis.com/css2?family=Bebas+Neue\&family=DM+Mono:wght@400;500\&family=Rajdhani:wght@400;500;600;700\&display=swap" rel="stylesheet"><!-- byteforge --></head>|' "$WWW/index.html"
  echo -e "\e[32m[  OK  ]\e[0m Fonts injected into index.html"
fi

# 4. Copy ByteForge SVG icons
SCRIPT_DIR="$(dirname "$0")"
if [ -f "$SCRIPT_DIR/byteforge-icon.svg" ]; then
  cp "$SCRIPT_DIR/byteforge-icon.svg" "$WWW/favicon.svg"
  # Also create a simple favicon.ico substitute
  cp "$SCRIPT_DIR/byteforge-icon.svg" "$WWW/img/byteforge-icon.svg"
  echo -e "\e[32m[  OK  ]\e[0m Icons deployed"
fi

if [ -f "$SCRIPT_DIR/byteforge-logo.svg" ]; then
  cp "$SCRIPT_DIR/byteforge-logo.svg" "$WWW/img/byteforge-logo.svg"
  echo -e "\e[32m[  OK  ]\e[0m Logo deployed"
fi

echo ""
echo -e "\e[38;5;208m  ⚒  ByteForge theme deployed! Genindlæs browseren med Ctrl+Shift+R  ⚒\e[0m"
echo ""
