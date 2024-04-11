#!/bin/bash
set -e
qemu_arm_flags=$(grep flags: /proc/sys/fs/binfmt_misc/qemu-arm | cut -d' ' -f2)
if ! echo "$qemu_arm_flags" | grep -q F; then
  echo "INFO: Enabling linux/arm/v7 docker builds with qmeu"
  docker run --privileged --rm tonistiigi/binfmt --install linux/arm/v7
fi
script="
apt update
apt install -y \\
  protobuf-compiler \\
  libfuse-dev \\
  pkgconf
cp -a /opt/lib/nuitka .venv
source /opt/lib/nuitka/bin/activate
pip install --upgrade pip build
make -C /src \"\$@\"
"
docker run \
  --rm \
  --platform=linux/arm/v7 \
  -v "$(pwd)":/src \
  eeems/nuitka-arm-builder:bullseye-3.11 \
  bash -ec "$script" -- "$@"
