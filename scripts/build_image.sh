#!/bin/bash

set -e

IMAGE="$1"

BASE="./sandbox/image/base_rootfs"
TEMP="./sandbox/image/${IMAGE}_rootfs"
FINAL="./sandbox/image/${IMAGE}"

if [ -z "$IMAGE" ]; then
    echo "Usage: $0 <python|gcc>"
    exit 1
fi

echo "========================================"
echo "[Build] Building image: $IMAGE"
echo "========================================"

#
# Check base_rootfs
#
if [ ! -d "$BASE" ]; then
    echo "[Build] base_rootfs not found"
    echo "Please run build_base.sh first"
    exit 1
fi

#
# Cleanup old image
#
sudo rm -rf "$TEMP"
sudo rm -rf "$FINAL"

#
# Copy base rootfs
#
echo "[Build] Copying base_rootfs..."

sudo mkdir -p "$TEMP"

sudo cp -a "$BASE/." "$TEMP/"

#
# Prepare chroot environment
#
echo "[Build] Mounting system dirs..."

sudo mount --bind /dev "$TEMP/dev"
sudo mount --bind /proc "$TEMP/proc"
sudo mount --bind /sys "$TEMP/sys"

sudo cp /etc/resolv.conf "$TEMP/etc/resolv.conf"

#
# Install packages
#
echo "[Build] Installing packages..."

if [ "$IMAGE" = "python" ]; then

    sudo chroot "$TEMP" /bin/sh -c "
        apk update &&
        apk add python3
    "

elif [ "$IMAGE" = "gcc" ]; then

    sudo chroot "$TEMP" /bin/sh -c "
        apk update &&
        apk add gcc g++ musl-dev build-base
    "

else
    echo "[Build] Unsupported image: $IMAGE"

    sudo umount "$TEMP/dev" || true
    sudo umount "$TEMP/proc" || true
    sudo umount "$TEMP/sys" || true

    exit 1
fi

#
# Cleanup mounts
#
echo "[Build] Cleaning mounts..."

sudo umount "$TEMP/dev"
sudo umount "$TEMP/proc"
sudo umount "$TEMP/sys"

#
# Generate diff layer
#
echo "[Build] Generating diff layer..."

sudo mkdir -p "$FINAL"

sudo rsync -a \
  --compare-dest="$(pwd)/$BASE/" \
  --exclude='/dev/**' \
  --exclude='/proc/**' \
  --exclude='/sys/**' \
  --exclude='/tmp/**' \
  --exclude='/run/**' \
  --exclude='/mnt/**' \
  --exclude='/media/**' \
  --exclude='/root/**' \
  --exclude='/var/cache/**' \
  --exclude='/var/log/**' \
  "$TEMP/" \
  "$FINAL/"

#
# Remove temp rootfs
#
echo "[Build] Removing temp rootfs..."

sudo rm -rf "$TEMP"

echo
echo "========================================"
echo "[Build] Image ready:"
echo "  $FINAL"
echo "========================================"