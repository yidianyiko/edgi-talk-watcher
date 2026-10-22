"""Check dependencies against the generated board config before invoking SCons."""
import re
import sys
from pathlib import Path


def check(path):
    text = Path(path).read_text()
    defines = dict(re.findall(r"^#define\s+(\w+)([^\n]*)", text, re.M))
    required = (
        "WATCH_VOICE_ENABLED", "WATCH_NETWORK_ENABLED", "RT_USING_AUDIO",
        "BSP_USING_AUDIO", "BSP_USING_AUDIO_RECORD", "BSP_USING_AUDIO_PLAY",
        "RT_USING_I2C", "BSP_USING_I2C", "BSP_USING_HW_I2C0",
    )
    missing = [key for key in required if key not in defines]
    if missing:
        raise ValueError("voice/audio boot dependencies missing: " + ", ".join(missing))
    if int(defines.get("FINSH_CMD_SIZE", "0")) < 256:
        raise ValueError("voice provisioning requires FINSH_CMD_SIZE >= 256")
    if "ENABLE_STEREO_INPUT_FEED" in defines:
        raise ValueError("voice PCM upload requires the official mono PDM mode")
    print("voice config: microphone, codec boot I2C0 and command buffer dependencies passed")


if __name__ == "__main__":
    check(sys.argv[1])
