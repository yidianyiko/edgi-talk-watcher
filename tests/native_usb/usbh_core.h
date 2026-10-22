#ifndef WATCH_TEST_USBH_CORE_H
#define WATCH_TEST_USBH_CORE_H
#include <stdint.h>
int usbh_deinitialize(uint8_t busid);
int usbh_initialize(uint8_t busid, uintptr_t reg_base, void *callback);
void *usbh_find_class_instance(const char *name);
#endif
