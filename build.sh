#!/bin/zsh
set -eu
PROJECT="${0:A:h}"
BUILD_PYTHON="${CALM_BUILD_PYTHON:-$PROJECT/.build-env/bin/python}"
STAGE="${CALM_BUILD_STAGE:-/tmp/calm-translate-source-build}"
APP="$STAGE/Trailk.app"
mkdir -p "$STAGE"
# Build artifacts only. Original prototypes, decisions, ledgers and Keychain are untouched.
swiftc -module-cache-path /tmp/calm-desktop-module-cache -target arm64-apple-macos14.4 "$PROJECT/src/main.swift" "$PROJECT/src/verification.swift" -o "$STAGE/CalmTranslate"
swift -module-cache-path /tmp/calm-desktop-module-cache "$PROJECT/src/icon.swift" "$STAGE/icon.png"
mkdir -p "$STAGE/AppIcon.iconset"
for n in 16 32 128 256 512; do
  sips -z "$n" "$n" "$STAGE/icon.png" --out "$STAGE/AppIcon.iconset/icon_${n}x${n}.png" >/dev/null
  nn=$((n * 2))
  sips -z "$nn" "$nn" "$STAGE/icon.png" --out "$STAGE/AppIcon.iconset/icon_${n}x${n}@2x.png" >/dev/null
done
iconutil -c icns "$STAGE/AppIcon.iconset" -o "$STAGE/AppIcon.icns"
PYINSTALLER_CONFIG_DIR=/tmp/calm-pyi-config "$BUILD_PYTHON" -m PyInstaller --noconfirm --clean --onedir --console --name calm-backend --distpath "$STAGE/dist" --workpath "$STAGE/work" --specpath "$STAGE" --paths "$PROJECT/src" --add-data "$PROJECT/assets/web:web" --add-data "$PROJECT/assets/seeds:seeds" --add-data "$PROJECT/assets/replay.json:." --add-data "$PROJECT/assets/ThirdParty:ThirdParty" --add-data "$PROJECT/assets/PROVENANCE.md:." --add-data "$PROJECT/assets/AudioCap-LICENSE.txt:." "$PROJECT/src/backend_entry.py"
if [[ -e "$APP" ]]; then
  echo 'Refusing to overwrite existing stage app. Use a fresh stage directory for another release.' >&2
  exit 1
fi
mkdir -p "$APP/Contents/MacOS" "$APP/Contents/Resources"
cp "$STAGE/CalmTranslate" "$APP/Contents/MacOS/CalmTranslate"
ditto "$STAGE/dist/calm-backend" "$APP/Contents/Resources/backend"
if [[ -n "${CALM_KEYCHAIN_HELPER:-}" ]]; then
  # Explicit existing helper path only: preserve code identity, never discover/read credentials.
  cp "$CALM_KEYCHAIN_HELPER" "$APP/Contents/Resources/keychain-bridge"
else
  swiftc -module-cache-path /tmp/calm-desktop-module-cache -target arm64-apple-macos26.0 "$PROJECT/keychain/KeychainBridge.swift" -o "$APP/Contents/Resources/keychain-bridge"
fi
cp "$STAGE/AppIcon.icns" "$APP/Contents/Resources/AppIcon.icns"
CAPTURE="$APP/Contents/Resources/Calm Capture.app"
mkdir -p "$CAPTURE/Contents/MacOS" "$CAPTURE/Contents/Resources"
swiftc -module-cache-path /tmp/calm-desktop-module-cache -target arm64-apple-macos14.4 "$PROJECT/src/capture/CaptureCore.swift" "$PROJECT/src/capture/main.swift" -o "$CAPTURE/Contents/MacOS/CalmCapture"
cp "$PROJECT/assets/public/public-irish.wav" "$CAPTURE/Contents/Resources/public-irish.wav"
cp "$PROJECT/assets/public/source.json" "$CAPTURE/Contents/Resources/PUBLIC-SOURCE.json"
cp "$PROJECT/assets/AudioCap-LICENSE.txt" "$CAPTURE/Contents/Resources/AudioCap-LICENSE.txt"
cp "$PROJECT/assets/PROVENANCE.md" "$CAPTURE/Contents/Resources/SOURCE-NOTICE.txt"
"$BUILD_PYTHON" - "$APP" <<'PY'
import plistlib,sys
from pathlib import Path
p=Path(sys.argv[1])/'Contents/Info.plist'
p.write_bytes(plistlib.dumps({'CFBundleIdentifier':'local.calmtranslate.desktop','CFBundleName':'Trailk','CFBundleDisplayName':'Trailk','CFBundleExecutable':'CalmTranslate','CFBundlePackageType':'APPL','CFBundleShortVersionString':'1.5.2','CFBundleVersion':'16','CFBundleIconFile':'AppIcon','LSMinimumSystemVersion':'26.0','NSHighResolutionCapable':True,'NSSupportsAutomaticTermination':False,'NSSupportsSuddenTermination':False,'NSAppTransportSecurity':{'NSAllowsLocalNetworking':True}}))
capture=Path(sys.argv[1])/'Contents/Resources/Calm Capture.app/Contents/Info.plist'
capture.write_bytes(plistlib.dumps({'CFBundleIdentifier':'local.calmtranslate.desktop.capture','CFBundleName':'Trailk Audio','CFBundleDisplayName':'Trailk · звук Zoom','CFBundleExecutable':'CalmCapture','CFBundlePackageType':'APPL','CFBundleVersion':'1','LSMinimumSystemVersion':'14.4','NSAudioCaptureUsageDescription':'Capture only the selected Zoom output or this helper public test audio. No microphone or screen capture.'}))
PY
codesign --force --sign - --identifier local.calmtranslate.desktop.capture "$CAPTURE"
codesign --force --sign - --identifier local.calmtranslate.desktop "$APP/Contents/MacOS/CalmTranslate"
codesign --force --sign - --identifier local.calmtranslate.desktop "$APP"
codesign --verify --strict --deep "$APP"
echo "Prepared $APP (ad-hoc local signing; no notarization)"
