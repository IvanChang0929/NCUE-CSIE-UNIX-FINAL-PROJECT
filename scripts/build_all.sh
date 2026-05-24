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

bash "$SCRIPT_DIR/build_base.sh"

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

echo
echo "========================================"
echo "[Build] All images ready"
echo "========================================"