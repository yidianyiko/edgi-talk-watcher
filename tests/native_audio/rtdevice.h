#ifndef TEST_RTDEVICE_H
#define TEST_RTDEVICE_H
#include "rtthread.h"
#define RT_PIPE_FLAG_BLOCK_RD 0x01
#define RT_PIPE_FLAG_FORCE_WR 0x04
struct rt_device {int unused;};
typedef struct rt_device *rt_device_t;
struct rt_audio_pipe {int flag;};
struct rt_audio_record {struct rt_audio_pipe pipe;};
struct rt_audio_device {struct rt_device parent;struct rt_audio_record *record;};
rt_ssize_t rt_device_read(rt_device_t device,int pos,void *data,size_t count);
#endif
