#ifndef WATCH_VOICE_CAPTURE_H
#define WATCH_VOICE_CAPTURE_H
#include <rtdevice.h>
#include <stddef.h>
int watch_voice_record(rt_device_t mic,unsigned char *pcm,size_t target,uint32_t deadline_ms,size_t *used);
#endif
