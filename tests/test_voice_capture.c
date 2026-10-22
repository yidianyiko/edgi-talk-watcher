#include "voice_capture.h"
#include <assert.h>
#include <stdio.h>
#include <string.h>
static uint32_t tick;
static unsigned reads,empty,available=0;
rt_base_t rt_hw_interrupt_disable(void){return 0;}
void rt_hw_interrupt_enable(rt_base_t value){(void)value;}
uint32_t rt_tick_get_millisecond(void){return tick;}
void rt_thread_mdelay(unsigned ms){tick+=ms;}
rt_ssize_t rt_device_read(rt_device_t device,int pos,void *data,size_t count) {
 struct rt_audio_device *audio=(struct rt_audio_device*)device;(void)pos;reads++;
 /* The installed audio_pipe.c blocks forever on an empty BLOCK_RD pipe. */
 assert(!(audio->record->pipe.flag & RT_PIPE_FLAG_BLOCK_RD));
 if(empty)return 0;
 if(count>available)count=available;
 memset(data,1,count);available-=(unsigned)count;return (rt_ssize_t)count;
}
int main(void) {
 struct rt_audio_record record={{RT_PIPE_FLAG_FORCE_WR|RT_PIPE_FLAG_BLOCK_RD}};
 struct rt_audio_device mic={{0},&record};unsigned char pcm[32000];size_t used=999;
 empty=1;
 assert(watch_voice_record((rt_device_t)&mic,pcm,sizeof(pcm),3000,&used)<0);
 assert(used==0&&tick==3000&&reads>0);
 assert(record.pipe.flag==(RT_PIPE_FLAG_FORCE_WR|RT_PIPE_FLAG_BLOCK_RD));
 /* Partial recording must also terminate and restore the original mode. */
 empty=0;available=320;tick=0;used=0;
 assert(watch_voice_record((rt_device_t)&mic,pcm,sizeof(pcm),3000,&used)<0);
 assert(used==320&&tick==3000);
 assert(record.pipe.flag==(RT_PIPE_FLAG_FORCE_WR|RT_PIPE_FLAG_BLOCK_RD));
 available=32000;tick=0;
 assert(!watch_voice_record((rt_device_t)&mic,pcm,sizeof(pcm),3000,&used));
 assert(used==32000&&tick==0);
 assert(record.pipe.flag==(RT_PIPE_FLAG_FORCE_WR|RT_PIPE_FLAG_BLOCK_RD));
 mic.record=NULL;
 assert(watch_voice_record((rt_device_t)&mic,pcm,sizeof(pcm),3000,&used)<0);
 puts("voice capture: empty and partial input deadline, nonblocking reads and restore passed");return 0;
}
