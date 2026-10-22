#!/usr/bin/env bash
set -euo pipefail
cd "$(dirname "$0")/.."
# Build the reviewed status image first, then use a separate combined project.
bash tools/build_board_status.sh
python3 - <<'PY'
from pathlib import Path
import shutil,re
base=Path('vendor/edgi-talk-bsp/projects/Edgi_Talk_CherryUSB')
src=base/'Edgi_Talk_M55_Watcher'; dst=base/'Edgi_Talk_M55_Watcher_Network'
wifi=base.parent/'Edgi_Talk_M55_WIFI'
if not dst.exists(): shutil.copytree(src,dst,symlinks=True,ignore=shutil.ignore_patterns('build','*.elf','*.hex','*.map','.sconsign*'))
sconstruct=(src/'SConstruct').read_text()
if "Export('env')" not in sconstruct: sconstruct=sconstruct.replace("Export('rtconfig')","Export('rtconfig')\nExport('env')")
(dst/'SConstruct').write_text(sconstruct)
# lwIP pools need 140 KiB: use M55 secondary SRAM, reduce heap by same size.
# Keep zero-table initialization; no M33 memory or flash mapping changes.
link=(src/'board/linker_scripts/link.ld').read_text()
link=link.replace('    .bss(NOLOAD) :', '''    .network_bss(NOLOAD) :
    {
        . = ALIGN(4);
        __network_bss_start__ = .;
        *memp.o(.bss*)
        . = ALIGN(4);
        __network_bss_end__ = .;
    } > m55_data_secondary
    .bss(NOLOAD) :''')
link=link.replace('        LONG(__bss_start__)', '''        LONG(__network_bss_start__)
        LONG((__network_bss_end__ - __network_bss_start__)/4)
        LONG(__bss_start__)''')
(dst/'board/linker_scripts/link.ld').write_text(link)
for path in Path('firmware/status').glob('*.[ch]'): shutil.copy2(path,dst/'applications'/path.name)
shutil.copy2(wifi/'packages'/'SConscript',dst/'packages'/'SConscript')
for name in ['FreeRTOS_Wrapper-latest']:
 shutil.copytree(wifi/'packages'/name,dst/'packages'/name,dirs_exist_ok=True)
shutil.copytree(wifi/'resources',dst/'resources',dirs_exist_ok=True)
config=(src/'rtconfig.h').read_text()
existing=set(re.findall(r'^#define\s+(\w+)',config,re.M))
# The vendor WiFi example is the source for exact flags and values.
excluded={'RT_WLAN_AUTO_CONNECT_ENABLE','AUTO_CONNECTION_PERIOD_MS','RT_WLAN_CFG_ENABLE','RT_WLAN_CFG_INFO_MAX','WHD_RESOURCES_IN_EXTERNAL_STORAGE_FAL','WHD_RESOURCES_FIRMWARE_PART_NAME','WHD_RESOURCES_CLM_PART_NAME','WHD_RESOURCES_NVRAM_PART_NAME','BSP_USING_FILESYSTEM','BSP_USING_SDCARD','BSP_USING_FLASH','BSP_USING_LITTLEFS','RT_USING_FAL','FAL_DEBUG','FAL_PART_HAS_TABLE_CFG','RT_USING_RYM'}
add=[]
for line in (wifi/'rtconfig.h').read_text().splitlines():
 m=re.match(r'#define\s+(\w+)',line)
 if m and m[1] not in existing|excluded:
  add.append(line);existing.add(m[1])
add+=['#define WHD_RESOURCES_IN_MEMORY','#define WATCH_NETWORK_ENABLED']
config=config.rsplit('#endif',1)[0]+'\n/* Combined WiFi options from pinned official M55_WIFI; no auto join. */\n'+'\n'.join(add)+'\n#endif\n'
(dst/'rtconfig.h').write_text(config)
PY
project=vendor/edgi-talk-bsp/projects/Edgi_Talk_CherryUSB/Edgi_Talk_M55_Watcher_Network
RTT_EXEC_PATH="${RTT_EXEC_PATH:-/usr/bin}" scons -C "$project" -j8
arm-none-eabi-objcopy -O binary "$project/rt-thread.elf" artifacts/product-completion/board/watcher-network-v4.bin
arm-none-eabi-objdump -h "$project/rt-thread.elf" > artifacts/product-completion/board/network-v4-sections.txt
stat -c '%s %n' artifacts/product-completion/board/watcher-network-v4.bin
sha256sum artifacts/product-completion/board/watcher-network-v4.bin
