#include "camera_recovery.h"
#include <rtthread.h>
#ifdef WATCH_VOICE_ENABLED
#include "usbh_core.h"
int watch_camera_recover(int busy, uintptr_t reg_base)
{
    unsigned elapsed;
    if (busy) return -2;
    if (usbh_deinitialize(0) || usbh_initialize(0,reg_base,0)) return -1;
    for (elapsed=0; elapsed<8000; elapsed+=100) {
        if (usbh_find_class_instance("/dev/video0")) return 0;
        rt_thread_mdelay(100);
    }
    return usbh_find_class_instance("/dev/video0") ? 0 : -1;
}
#endif
