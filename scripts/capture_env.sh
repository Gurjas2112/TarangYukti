# Shared settings for the walkthrough capture scripts (spec §17.14), on Windows Git Bash.
# Override any of these in the environment; the defaults match Android Studio + Maestro in the user folder.
SDK=${ANDROID_SDK_ROOT:-${LOCALAPPDATA:-$HOME/AppData/Local}/Android/Sdk}
ADB=${ADB:-$SDK/platform-tools/adb.exe}
EMULATOR=${EMULATOR:-$SDK/emulator/emulator.exe}
AVD=${AVD:-ty_pixel}
PKG=in.tarangyukti.kadalmitra
MAESTRO=${MAESTRO:-$USERPROFILE/maestro/bin/maestro}
export JAVA_HOME=${JAVA_HOME_17:-"/c/Program Files/Android/Android Studio/jbr"}
CHANNELS_LOCAL=${CHANNELS_LOCAL:-http://127.0.0.1:8002}
# CAPTURE_TOKEN comes from the git-ignored .env (laptop only)
if [ -z "${CAPTURE_TOKEN:-}" ] && [ -f .env ]; then
  CAPTURE_TOKEN=$(grep -E '^CAPTURE_TOKEN=' .env | cut -d= -f2- || true)
fi
