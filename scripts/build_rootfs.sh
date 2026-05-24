#!/bin/bash

set -e

ALPINE_VERSION="3.19.9"

BASE_DIR="./sandbox/image/base_rootfs"

TMP_FILE="/tmp/alpine-minirootfs.tar.gz"

URL="https://dl-cdn.alpinelinux.org/alpine/v3.19/releases/x86_64/alpine-minirootfs-${ALPINE_VERSION}-x86_64.tar.gz"

echo "========================================"
echo "[Build] Download Alpine Minirootfs"
echo "========================================"

#
# Cleanup old base
#
sudo rm -rf "$BASE_DIR"

mkdir -p "$BASE_DIR"

#
# Download alpine minirootfs
#
echo "[Build] Downloading Alpine..."

wget -O "$TMP_FILE" "$URL"

#
# Extract
#
echo "[Build] Extracting rootfs..."

sudo tar -xzf "$TMP_FILE" -C "$BASE_DIR"

#
# Cleanup
#
rm -f "$TMP_FILE"

echo
echo "========================================"
echo "[Build] Alpine base_rootfs ready"
echo "  $BASE_DIR"
echo "========================================"