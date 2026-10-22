#include <assert.h>
#include <pthread.h>
#include <stdint.h>
#include <stdio.h>
#include <string.h>
#include <time.h>
#include "rtthread.h"
#include "board.h"
#include "usb_dwc2_reg.h"
struct usbh_video { int present; };
uint32_t test_usb_registers[512];
static struct usbh_video video;
static unsigned irq_enabled, dangling_irq, resubmitted, closed, killed, freed;
static int stop_without_device, stop_close_error, nested_close, close_has_irq;
static unsigned channel_has_urb, vendor_recover_wakes;
static volatile unsigned active_stops;
void __real_usbh_video_transfer_abort_callback(void) { vendor_recover_wakes++; }
void __wrap_usbh_video_transfer_abort_callback(void);
static DWC2_HostChannelTypeDef *channel(unsigned i) {
 return (void *)((uintptr_t)test_usb_registers+USB_OTG_HOST_CHANNEL_BASE+i*USB_OTG_HOST_CHANNEL_SIZE);
}
static void dispatch(void) {
 if (irq_enabled && (channel(0)->HCINT & channel(0)->HCINTMSK)) {
  if (!channel_has_urb) dangling_irq++;
 }
 /* A successful second completion can re-submit the first freed global URB. */
 if (irq_enabled && freed==1 && killed==1) resubmitted++;
}
unsigned NVIC_GetEnableIRQ(int irq) { assert(irq==151); return irq_enabled; }
void NVIC_DisableIRQ(int irq) { assert(irq==151); irq_enabled=0; }
void NVIC_EnableIRQ(int irq) { assert(irq==151); irq_enabled=1; dispatch(); }
int rt_mutex_init(struct rt_mutex *m,const char *name,unsigned flags) {
 (void)name;(void)flags; return pthread_mutex_init(&m->native,0);
}
int rt_mutex_take(struct rt_mutex *m,int timeout) { (void)timeout; return pthread_mutex_lock(&m->native); }
int rt_mutex_release(struct rt_mutex *m) { return pthread_mutex_unlock(&m->native); }
rt_thread_t rt_thread_self(void) { return (rt_thread_t)pthread_self(); }
void *usbh_find_class_instance(const char *name) { assert(!strcmp(name,"/dev/video0")); return stop_without_device?0:&video; }
int __real_usbh_video_close(struct usbh_video *v) {
 assert(v==&video); closed++; close_has_irq=irq_enabled;
 return stop_close_error?-1:0;
}
int __wrap_usbh_video_close(struct usbh_video *v);
void __real_usbh_video_stream_stop(void) {
 struct timespec pause={0,1000000};
 assert(__sync_add_and_fetch(&active_stops,1)==1);
 nanosleep(&pause,0);
 if (!stop_without_device) __wrap_usbh_video_close(&video);
 /* Reproduce dwc2_halt's early return: CHENA=0 leaves HALTED unmasked.
    usbh_kill_urb then clears channel->urb and restores CPU interrupt mask. */
 channel_has_urb=0; killed=1; dispatch();
 freed=1; dispatch();
 killed=2; dispatch(); freed=2;
 assert(__sync_sub_and_fetch(&active_stops,1)==0);
}
#ifdef WATCH_TEST_UNPATCHED
int __wrap_usbh_video_close(struct usbh_video *v) { return __real_usbh_video_close(v); }
void __wrap_usbh_video_stream_stop(void) { __real_usbh_video_stream_stop(); }
int test_camera_stop_init(void) { return 0; }
void __wrap_usbh_video_transfer_abort_callback(void) { __real_usbh_video_transfer_abort_callback(); }
#else
void __wrap_usbh_video_stream_stop(void);
int test_camera_stop_init(void);
#endif
static void reset(void) {
 memset(test_usb_registers,0,sizeof(test_usb_registers));
 irq_enabled=1; dangling_irq=resubmitted=closed=killed=freed=0;
 channel_has_urb=1; stop_without_device=stop_close_error=nested_close=0;
 channel(0)->HCINT=2;channel(0)->HCINTMSK=2;
}
static void *parallel_stop(void *unused) { (void)unused; __wrap_usbh_video_stream_stop(); return 0; }
int main(void) {
 pthread_t first,second;
 assert(test_camera_stop_init()==0);
 reset(); __wrap_usbh_video_stream_stop();
 assert(close_has_irq==1); assert(dangling_irq==0); assert(resubmitted==0);
 assert(irq_enabled==1); assert(killed==2 && freed==2);
 assert(channel(0)->HCINTMSK==0);
 reset(); irq_enabled=0; __wrap_usbh_video_stream_stop(); assert(!irq_enabled);
 reset(); stop_without_device=1; __wrap_usbh_video_stream_stop(); assert(!closed && !dangling_irq && !resubmitted && irq_enabled);
 reset(); stop_close_error=1; __wrap_usbh_video_stream_stop(); assert(!dangling_irq && !resubmitted && irq_enabled);
 reset(); assert(__wrap_usbh_video_close(&video)==0); assert(irq_enabled && channel(0)->HCINTMSK==2);
 reset(); assert(!pthread_create(&first,0,parallel_stop,0)); assert(!pthread_create(&second,0,parallel_stop,0));
 pthread_join(first,0);pthread_join(second,0); assert(!active_stops && closed==2 && irq_enabled && !dangling_irq);
 vendor_recover_wakes=0; __wrap_usbh_video_transfer_abort_callback(); assert(vendor_recover_wakes==0);
 puts("camera stop pending-IRQ, paired cancellation, close, missing-device and NVIC preservation tests passed");
}
