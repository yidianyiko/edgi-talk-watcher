#include "camera_recovery.h"
#include <assert.h>
#include <stdint.h>
#include <stdio.h>
#include <string.h>
static unsigned operations, elapsed, found_after;
static int deinit_error, init_error;
int usbh_deinitialize(uint8_t bus) { assert(bus==0); assert(operations==0); operations=1; return deinit_error; }
int usbh_initialize(uint8_t bus,uintptr_t base,void *callback) { assert(bus==0);assert(base==0x12340000);assert(callback==0);assert(operations==1);operations=2;return init_error; }
void *usbh_find_class_instance(const char *name) { assert(!strcmp(name,"/dev/video0"));assert(operations==2);return elapsed>=found_after?(void *)1:0; }
void rt_thread_mdelay(unsigned milliseconds) { elapsed+=milliseconds; }
static void reset(void){operations=elapsed=deinit_error=init_error=0;found_after=300;}
int main(void){
 reset();assert(watch_camera_recover(1,0x12340000)==-2);assert(operations==0);
 reset();assert(watch_camera_recover(0,0x12340000)==0);assert(elapsed==300);assert(operations==2);
 reset();found_after=9000;assert(watch_camera_recover(0,0x12340000)==-1);assert(elapsed==8000);
 reset();deinit_error=-1;assert(watch_camera_recover(0,0x12340000)==-1);assert(operations==1);
 reset();init_error=-1;assert(watch_camera_recover(0,0x12340000)==-1);assert(operations==2);assert(elapsed==0);
 puts("PASS camera recovery: busy rejects, ordered host restart, reenumeration and bounded missing/error paths");
}
