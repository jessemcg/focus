#!/bin/sh
# Public bootstrap: install the latest main source.
set -eu
umask 077
ref='main'
[ "$(id -u)" != 0 ] || { printf '[FAIL] Run as the desktop user.\n'; exit 1; }
[ ! -e /run/ostree-booted ] && [ ! -d /sysroot/ostree ] || { printf '[FAIL] Immutable desktop unsupported.\n'; exit 1; }
. /etc/os-release
family=''
case "${ID:-}:${VARIANT_ID:-}" in bazzite:*|silverblue:*|kinoite:*|fedora:silverblue|fedora:kinoite|fedora:coreos) exit 1 ;; esac
if [ "${ID:-}" = ubuntu ]; then
  case "${VERSION_ID:-}" in 24.04|26.04) ;; *) printf '[FAIL] Unsupported Ubuntu release.\n'; exit 1 ;; esac
fi
case " ${ID:-} ${ID_LIKE:-} " in
  *' ubuntu '*)
    case "${UBUNTU_VERSION_ID:-${VERSION_ID:-}}:${UBUNTU_CODENAME:-}" in
      24.04:*|26.04:*|*:noble|*:resolute) family=apt ;;
      *) printf '[FAIL] Unsupported Ubuntu base.\n'; exit 1 ;;
    esac ;;
  *' fedora '*)
    case "${FEDORA_VERSION_ID:-${VERSION_ID:-}}" in 43|44) family=dnf ;; *) exit 1 ;; esac ;;
  *) printf '[FAIL] Unsupported distro/base.\n'; exit 1 ;;
esac
case "$(uname -m)" in x86_64|aarch64) ;; *) exit 1 ;; esac
temp=$(mktemp -d -t focus-download.XXXXXXXX) || exit 1
trap 'rm -rf -- "$temp"' EXIT HUP INT TERM
snapshot() {
  if [ "$family" = apt ]; then
    dpkg-query -W '-f=${binary:Package}\t${db:Status-Status}\n' | awk '$2 == "installed" {sub(/:.*/, "", $1);print $1}' | sort -u
  else rpm -qa --qf '%{NAME}\n' | sort -u; fi
}
introduced=''
if ! command -v curl >/dev/null 2>&1 && ! command -v wget >/dev/null 2>&1; then
  printf '[ACTION] No downloader. Preview installing curl from official repositories.\n'
  snapshot > "$temp/before"
  if [ "$family" = apt ]; then
    apt-get --simulate install curl > "$temp/preview"
    more "$temp/preview"
    if grep -q '^Remv ' "$temp/preview"; then printf '[FAIL] Transaction would remove packages.\n'; exit 1; fi
  else
    dnf --assumeno install curl || [ "$?" = 1 ]
  fi
  printf '[WAIT] Authorize curl transaction (sudo still asks separately)? Type yes: ' >/dev/tty
  IFS= read -r answer </dev/tty
  [ "$answer" = yes ] || exit 1
  if [ "$family" = apt ]; then sudo apt-get install curl; else sudo dnf install curl; fi
  snapshot > "$temp/after"
  introduced=$(comm -13 "$temp/before" "$temp/after" | tr '\n' ' ')
  printf '[WARN] Bootstrap-introduced packages retained if later download fails: %s\n' "$introduced"
fi
url="https://raw.githubusercontent.com/jessemcg/focus/$ref/install.sh"
printf '[ACTION] Download COMPLETE script from %s\n' "$url"
if command -v curl >/dev/null 2>&1; then
  curl -fL --proto '=https' --tlsv1.2 "$url" -o "$temp/install.sh"
else wget --https-only -O "$temp/install.sh" "$url"; fi
printf '[WAIT] Script downloaded to %s. Inspect before execution? [Y/n] ' "$temp/install.sh" >/dev/tty
IFS= read -r inspect </dev/tty
case "$inspect" in n|N) ;; *) if command -v less >/dev/null 2>&1; then less "$temp/install.sh" </dev/tty; else more "$temp/install.sh" </dev/tty; fi ;; esac
printf '[WAIT] Execute the inspected source installer? Type yes: ' >/dev/tty
IFS= read -r answer </dev/tty
[ "$answer" = yes ] || exit 1
FOCUS_INSTALL_REF="$ref" FOCUS_BOOTSTRAP_PACKAGES="$introduced" bash "$temp/install.sh" "$@" </dev/tty
