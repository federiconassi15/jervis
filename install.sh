#!/bin/sh
set -eu

REPO="federiconassi15/jervis"
BASE="https://github.com/$REPO/releases/latest/download"

say() { printf '%s\n' "$*"; }
die() { say "Jervis installer: $*" >&2; exit 1; }

as_root() {
    if [ "$(id -u)" -eq 0 ]; then
        "$@"
    elif command -v sudo >/dev/null 2>&1; then
        sudo "$@"
    else
        die "administrator privileges are required to install the download helper"
    fi
}

ensure_downloader() {
    if command -v curl >/dev/null 2>&1 || command -v wget >/dev/null 2>&1; then
        return
    fi

    say "Jervis: no downloader found; installing curl using the system package manager..."
    if command -v pacman >/dev/null 2>&1; then
        as_root pacman -Sy --needed --noconfirm curl ca-certificates
    elif command -v apt-get >/dev/null 2>&1; then
        as_root apt-get update
        as_root apt-get install -y curl ca-certificates
    elif command -v dnf >/dev/null 2>&1; then
        as_root dnf install -y curl ca-certificates
    elif command -v zypper >/dev/null 2>&1; then
        as_root zypper --non-interactive install curl ca-certificates
    elif command -v apk >/dev/null 2>&1; then
        as_root apk add curl ca-certificates
    else
        die "no curl/wget and no supported package manager were found"
    fi
}

fetch() {
    url="$1"
    out="$2"
    if command -v curl >/dev/null 2>&1; then
        curl -fL --retry 3 --connect-timeout 15 "$url" -o "$out"
    elif command -v wget >/dev/null 2>&1; then
        wget -O "$out" "$url"
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
trap 'rm -rf "$tmp"' EXIT HUP INT TERM

say "Jervis: downloading $asset..."
fetch "$BASE/$asset" "$tmp/$asset"
fetch "$BASE/SHA256SUMS" "$tmp/SHA256SUMS"
verify_sha256 "$tmp/$asset" "$tmp/SHA256SUMS" "$asset"
chmod +x "$tmp/$asset"

say "Jervis: verified. Starting installer..."
exec "$tmp/$asset"
