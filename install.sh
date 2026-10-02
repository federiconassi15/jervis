#!/bin/sh
set -eu

REPO="federiconassi15/jervis"
BASE="https://github.com/$REPO/releases/latest/download"
LOG="${TMPDIR:-/tmp}/jervis-bootstrap-$$.log"

say() { printf '%s\n' "$*"; }
die() { say "Jervis installer: $*" >&2; exit 1; }

cleanup() {
    rm -rf "${tmp:-}" 2>/dev/null || true
    rm -f "$LOG" 2>/dev/null || true
}
trap cleanup EXIT HUP INT TERM

as_root_quiet() {
    if [ "$(id -u)" -eq 0 ]; then
        "$@" >"$LOG" 2>&1 || {
            tail -n 24 "$LOG" >&2 || true
            return 1
        }
        return
    fi

    command -v sudo >/dev/null 2>&1 || die "administrator privileges are required"
    # Keep authentication visible, then keep the package manager itself quiet.
    sudo -v
    sudo -n env DEBIAN_FRONTEND=noninteractive APT_LISTCHANGES_FRONTEND=none         "$@" >"$LOG" 2>&1 || {
            tail -n 24 "$LOG" >&2 || true
            return 1
        }
}

ensure_downloader() {
    if command -v curl >/dev/null 2>&1 || command -v wget >/dev/null 2>&1; then
        return
    fi

    say "Jervis · preparing download support"
    if command -v pacman >/dev/null 2>&1; then
        as_root_quiet pacman -Sy --needed --noconfirm curl ca-certificates
    elif command -v apt-get >/dev/null 2>&1; then
        as_root_quiet apt-get -qq update
        as_root_quiet apt-get -qq install -y curl ca-certificates
    elif command -v dnf >/dev/null 2>&1; then
        as_root_quiet dnf -q -y install curl ca-certificates
    elif command -v zypper >/dev/null 2>&1; then
        as_root_quiet zypper --non-interactive --quiet install curl ca-certificates
    elif command -v apk >/dev/null 2>&1; then
        as_root_quiet apk add --quiet curl ca-certificates
    else
        die "no curl/wget and no supported package manager were found"
    fi
}

fetch() {
    url="$1"
    out="$2"
    if command -v curl >/dev/null 2>&1; then
        curl -fsSL --retry 3 --connect-timeout 15 "$url" -o "$out"
    elif command -v wget >/dev/null 2>&1; then
        wget -q -O "$out" "$url"
    else
        die "no downloader is available"
    fi
}

verify_sha256() {
    file="$1"
    sums="$2"
    name="$3"
    expected="$(awk -v n="$name" '$2 == n || $2 == "*" n {print $1; exit}' "$sums")"
    [ -n "$expected" ] || die "checksum entry for $name is missing"

    if command -v sha256sum >/dev/null 2>&1; then
        actual="$(sha256sum "$file" | awk '{print $1}')"
    elif command -v shasum >/dev/null 2>&1; then
        actual="$(shasum -a 256 "$file" | awk '{print $1}')"
    elif command -v openssl >/dev/null 2>&1; then
        actual="$(openssl dgst -sha256 "$file" | awk '{print $NF}')"
    else
        die "no SHA-256 tool is available"
    fi

    [ "$actual" = "$expected" ] || die "checksum verification failed"
}

os="$(uname -s 2>/dev/null || true)"
arch="$(uname -m 2>/dev/null || true)"

case "$os:$arch" in
    Linux:x86_64|Linux:amd64) asset="jervis-linux-x64" ;;
    Linux:aarch64|Linux:arm64) asset="jervis-linux-arm64" ;;
    Darwin:x86_64|Darwin:amd64) asset="jervis-macos-x64" ;;
    Darwin:arm64|Darwin:aarch64) asset="jervis-macos-arm64" ;;
    *) die "unsupported platform: ${os:-unknown} ${arch:-unknown}" ;;
esac

ensure_downloader

tmp="${TMPDIR:-/tmp}/jervis-install-$$"
mkdir -p "$tmp"

say "Jervis · downloading runtime"
fetch "$BASE/$asset" "$tmp/$asset"
fetch "$BASE/SHA256SUMS" "$tmp/SHA256SUMS"

say "Jervis · verifying release"
verify_sha256 "$tmp/$asset" "$tmp/SHA256SUMS" "$asset"
chmod +x "$tmp/$asset"

printf '\n'
say "┌─ JERVIS BOOTSTRAP ─────────────────────────────┐"
say "│ target   $asset"
say "│ verify   SHA-256 ✓"
say "│ state    native payload ready"
say "└─ launching installation control deck ──────────┘"
printf '\007'
sleep 0.06
printf '\007'
exec "$tmp/$asset"
