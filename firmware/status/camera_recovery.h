#ifndef WATCH_CAMERA_RECOVERY_H
#define WATCH_CAMERA_RECOVERY_H
#include <stdint.h>
/* Restart the USB host only while no capture worker owns it. */
int watch_camera_recover(int busy, uintptr_t reg_base);
#endif
