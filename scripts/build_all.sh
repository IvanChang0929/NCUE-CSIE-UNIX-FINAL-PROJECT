#!/bin/bash

set -e

SCRIPT_DIR="./scripts"

echo "========================================"
echo "[Build] Full Sandbox Image Build"
echo "========================================"

#
# Build base image
#
echo
echo "[1/3] Building Alpine base_rootfs..."

bash "$SCRIPT_DIR/build_rootfs.sh"

#
# Build gcc image
#
echo
echo "[2/3] Building GCC image..."

bash "$SCRIPT_DIR/build_image.sh" gcc

#
# Build python image
#
echo
echo "[3/3] Building Python image..."

bash "$SCRIPT_DIR/build_image.sh" python

sudo rm -rf ./sandbox/image/base_rootfs/bin
sudo rm -rf ./sandbox/image/base_rootfs/sbin
sudo rm -rf ./sandbox/image/base_rootfs/usr/bin
sudo rm -rf ./sandbox/image/base_rootfs/usr/sbin

#
# Recreate required runtime dirs
#
sudo mkdir -p ./sandbox/image/base_rootfs/bin
sudo mkdir -p ./sandbox/image/base_rootfs/lib
sudo mkdir -p ./sandbox/image/base_rootfs/tmp
sudo mkdir -p ./sandbox/image/base_rootfs/dev

#
# lib64 compatibility
#
if [ ! -e ./sandbox/image/base_rootfs/lib64 ]; then
    sudo ln -s lib ./sandbox/image/base_rootfs/lib64
fi

#
# Standard tmp permission
#
sudo chmod 1777 ./sandbox/image/base_rootfs/tmp


echo
echo "========================================"
echo "[Build] All images ready"
echo "========================================"