#!/bin/bash

set -e

ALPINE_VERSION="3.19.1" # 建議維持你原本或是穩定的 3.19 版本
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
# Cleanup temporary tarball
#
rm -f "$TMP_FILE"

# ──────────────────────────────────────────────────────────────────────
# ───【★ 核心自動化加固：實踐老師要求的 rootfs 最小化（No-Shell）★】───
# ──────────────────────────────────────────────────────────────────────
echo "[Build Security] Purging all shells and non-essential binaries..."

# 1. 物理抹殺所有的指令夾（斬草除根，消滅 busybox、sh、ash）
sudo rm -rf "$BASE_DIR/bin"
sudo rm -rf "$BASE_DIR/sbin"
sudo rm -rf "$BASE_DIR/usr/bin"
sudo rm -rf "$BASE_DIR/usr/sbin"

# 2. 依照安全規格，重新建立完全「空無一物」的必備結構資料夾
# 這樣可以確保沙箱內部掛載點（如 /bin, /tmp, /dev）有實體節點可以對齊
sudo mkdir -p "$BASE_DIR/bin"
sudo mkdir -p "$BASE_DIR/tmp"
sudo mkdir -p "$BASE_DIR/dev"

# 3. 確保動態連結庫目錄結構健在 (Alpine 預設使用 lib，我們補上 lib64 軟連結確保相容性)
sudo mkdir -p "$BASE_DIR/lib"
if [ ! -e "$BASE_DIR/lib64" ]; then
    sudo ln -s lib "$BASE_DIR/lib64"
fi

# 4. 調整暫存區權限，符合標準 Linux 系統的 777 權限
sudo chmod 1777 "$BASE_DIR/tmp"

echo "[Build Security] Whitelist-only directory structure initialized."
# ──────────────────────────────────────────────────────────────────────

echo
echo "========================================"
echo "[Build] Distroless No-Shell base_rootfs ready"
echo "  $BASE_DIR"
echo "========================================"