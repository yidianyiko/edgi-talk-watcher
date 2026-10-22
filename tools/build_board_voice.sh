#!/usr/bin/env bash
set -euo pipefail
cd "$(dirname "$0")/.."
# Separate voice build: retain reviewed V4 artifacts and the existing M33 image.
expected=b135be8a28127e276a04b70d27950c3ba07b917a
test "$(git -C vendor/edgi-talk-bsp rev-parse HEAD)" = "$expected" || { echo "BSP revision changed; inspect before building" >&2; exit 1; }
# The pinned BSP signals free buffers as completed frames at pool creation.
# Apply only the reviewed patch; accept exactly its already-applied state.
patch="$PWD/firmware/patches/camera-empty-queue.patch"
if git -C vendor/edgi-talk-bsp apply --check "$patch" 2>/dev/null; then
  git -C vendor/edgi-talk-bsp apply "$patch"
else
  git -C vendor/edgi-talk-bsp apply --reverse --check "$patch"
fi
mkdir -p artifacts/board-voice
camera_pool=vendor/edgi-talk-bsp/libraries/components/CherryUSB-1.6.0/third_party/cherrymp
cc -std=c99 -Wall -Wextra -Werror -Itests/native_camera -I"$camera_pool" tests/test_camera_pool.c "$camera_pool/chry_mempool.c" "$camera_pool/chry_mempool_osal_rtthread.c" -o artifacts/board-voice/test_camera_pool
cc -std=c99 -Wall -Wextra -Werror -DWATCH_VOICE_ENABLED -Itests/native_usb -Ifirmware/status tests/test_camera_recovery.c firmware/status/camera_recovery.c -o artifacts/board-voice/test_camera_recovery
artifacts/board-voice/test_camera_recovery
cc -std=c99 -Wall -Wextra -Werror -pthread -DWATCH_VOICE_ENABLED -Itests/native_usb -Ivendor/edgi-talk-bsp/libraries/components/CherryUSB-1.6.0/port/dwc2 tests/test_camera_stop.c firmware/status/camera_stop.c -o artifacts/board-voice/test_camera_stop
artifacts/board-voice/test_camera_stop
artifacts/board-voice/test_camera_pool
cc -std=c99 -Wall -Wextra -Werror -Ifirmware/status tests/test_voice_protocol.c firmware/status/voice_protocol.c -o artifacts/board-voice/test_voice
artifacts/board-voice/test_voice
cc -std=c99 -Wall -Wextra -Werror -DWATCH_VOICE_ENABLED -Itests/native_audio -Ifirmware/status tests/test_voice_capture.c firmware/status/voice_capture.c -o artifacts/board-voice/test_voice_capture
artifacts/board-voice/test_voice_capture
for pair in 'test_face face' 'test_announce_protocol announce_protocol' 'test_status status' 'test_board_product product' 'test_gateway gateway'; do
  read -r test_name module <<< "$pair"
  cc -std=c99 -Wall -Wextra -Werror -Ifirmware/status "tests/$test_name.c" "firmware/status/$module.c" -o "artifacts/board-voice/$test_name"
  "artifacts/board-voice/$test_name"
done
python3 - <<'PY'
from pathlib import Path
import shutil,re
base=Path('vendor/edgi-talk-bsp/projects/Edgi_Talk_CherryUSB')
src=base/'Edgi_Talk_M55_Watcher'; dst=base/'Edgi_Talk_M55_Watcher_Voice'
wifi=base.parent/'Edgi_Talk_M55_WIFI'
if not dst.exists(): shutil.copytree(src,dst,symlinks=True,ignore=shutil.ignore_patterns('build','*.elf','*.hex','*.map','.sconsign*'))
sconstruct=(src/'SConstruct').read_text()
if "Export('env')" not in sconstruct: sconstruct=sconstruct.replace("Export('rtconfig')","Export('rtconfig')\nExport('env')")
sconstruct=sconstruct.replace("Export('env')", "Export('env')\nenv.Append(CPPPATH=["+repr(str(Path('vendor/edgi-talk-bsp/libraries/components/CherryUSB-1.6.0/port/dwc2').resolve()))+"])\nenv['LINKFLAGS'] = env['LINKFLAGS'] + ' -Wl,--wrap=usbh_video_stream_stop,--wrap=usbh_video_close,--wrap=usbh_video_transfer_abort_callback'")
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
board=(src/'board/board.c').read_text().replace('rt_pin_write(SPEAKER_OE_CTRL, PIN_HIGH);','rt_pin_write(SPEAKER_OE_CTRL, PIN_LOW); /* microphone only */')
(dst/'board/board.c').write_text(board)
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
add+=['#define WHD_RESOURCES_IN_MEMORY','#define WATCH_NETWORK_ENABLED','#define WATCH_VOICE_ENABLED',
       '#define RT_USING_AUDIO','#define RT_AUDIO_REPLAY_MP_BLOCK_SIZE 4096',
       '#define RT_AUDIO_REPLAY_MP_BLOCK_COUNT 2','#define RT_AUDIO_RECORD_PIPE_SIZE 2048',
       '#define BSP_USING_AUDIO','#define BSP_USING_AUDIO_RECORD','#define BSP_USING_AUDIO_PLAY',
       '#define BSP_USING_HW_I2C0']
config=re.sub(r'(#define FINSH_CMD_SIZE)\s+\d+',r'\1 256',config)
config=config.rsplit('#endif',1)[0]+'\n/* Combined WiFi options from pinned official M55_WIFI; no auto join. */\n'+'\n'.join(add)+'\n#endif\n'
(dst/'rtconfig.h').write_text(config)
PY
project=vendor/edgi-talk-bsp/projects/Edgi_Talk_CherryUSB/Edgi_Talk_M55_Watcher_Voice
python3 tests/check_board_voice_config.py "$project/rtconfig.h"
RTT_EXEC_PATH="${RTT_EXEC_PATH:-/usr/bin}" scons -C "$project" -j8
arm-none-eabi-objcopy -O binary "$project/rt-thread.elf" artifacts/board-voice/watcher-voice-v10.bin
arm-none-eabi-objdump -h "$project/rt-thread.elf" > artifacts/board-voice/voice-v10-sections.txt
stat -c '%s %n' artifacts/board-voice/watcher-voice-v10.bin
sha256sum artifacts/board-voice/watcher-voice-v10.bin

# The existing four-sector M55 slot starts at +0x400 after its image header.
test "$(stat -c %s artifacts/board-voice/watcher-voice-v10.bin)" -le 1047552 || { echo "M55 voice image exceeds backed-up four-sector slot" >&2; exit 1; }

# Check the built artifact, not only rtconfig.h: conditional code must survive linking.
arm-none-eabi-nm "$project/rt-thread.elf" > artifacts/board-voice/voice-v10-symbols.txt
python3 - <<'CHECK'
from pathlib import Path
symbols={line.split()[-1] for line in Path('artifacts/board-voice/voice-v10-symbols.txt').read_text().splitlines() if line.split()}
assert {'__fsym_watch_announce','watch_alert_audio','watch_audio_claim','watch_face_draw','__fsym_watch_camera_reset','__wrap_usbh_video_stream_stop','__wrap_usbh_video_close','__wrap_usbh_video_transfer_abort_callback'} <= symbols, 'Voice or face code absent from ELF'
print('Voice announcement command, embedded speech and audio gate present in linked ELF')
CHECK
