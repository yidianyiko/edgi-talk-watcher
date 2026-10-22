#!/usr/bin/env bash
set -euo pipefail
cd "$(dirname "$0")/.."
upstream=vendor/edgi-talk-bsp
project=$upstream/projects/Edgi_Talk_CherryUSB/Edgi_Talk_M55_Watcher
if [ ! -d "$upstream/.git" ]; then
  git clone --depth 1 https://gitee.com/RT-Thread-Studio-Mirror/sdk-bsp-psoc_e84-edgi-talk.git "$upstream"
fi
expected=b135be8a28127e276a04b70d27950c3ba07b917a
test "$(git -C "$upstream" rev-parse HEAD)" = "$expected" || {
  echo "BSP revision changed; inspect before building" >&2; exit 1;
}
if [ ! -d "$project" ]; then
  cp -a "$upstream/projects/Edgi_Talk_CherryUSB/Edgi_Talk_M55_USB_UVC" "$project"
fi
mkdir -p artifacts/board-status
cc -std=c99 -Wall -Wextra -Werror -Ifirmware/status tests/test_status.c firmware/status/status.c -o artifacts/board-status/test_status
artifacts/board-status/test_status
cc -std=c99 -Wall -Wextra -Werror -Ifirmware/status tests/test_board_product.c firmware/status/product.c -o artifacts/board-status/test_product
artifacts/board-status/test_product
cc -std=c99 -Wall -Wextra -Werror -Ifirmware/status tests/test_gateway.c firmware/status/gateway.c -o artifacts/board-status/test_gateway
artifacts/board-status/test_gateway
cp firmware/status/*.[ch] "$project/applications/"
RTT_EXEC_PATH="${RTT_EXEC_PATH:-/usr/bin}" scons -C "$project" -j8
arm-none-eabi-objcopy -O binary "$project/rt-thread.elf" artifacts/board-status/watcher-v4.bin
arm-none-eabi-objdump -h "$project/rt-thread.elf" > artifacts/board-status/sections.txt
sha256sum artifacts/board-status/watcher-v4.bin
