#include "voice_capture.h"
#ifdef WATCH_VOICE_ENABLED
#include <rtthread.h>
int watch_voice_record(rt_device_t mic,unsigned char *pcm,size_t target,uint32_t deadline_ms,size_t *used) {
 struct rt_audio_device *audio=(struct rt_audio_device*)mic;
 rt_base_t level;rt_int32_t saved_flags;uint32_t start;int result=-1;
 if(!mic||!pcm||!target||!deadline_ms||!used)return -1;
 *used=0;
 if(!audio->record)return -1;
 /* This BSP uses drivers/audio/audio_pipe.c, not drivers/ipc/pipe.c.
  * audio.c creates BLOCK_RD|FORCE_WR; an empty blocking read has no timeout.
  * No other reader is permitted while this recorder owns mic0. Retain ISR
  * FORCE_WR, clear BLOCK_RD atomically, and restore on every exit. */
 level=rt_hw_interrupt_disable();saved_flags=audio->record->pipe.flag;
 audio->record->pipe.flag &= ~RT_PIPE_FLAG_BLOCK_RD;rt_hw_interrupt_enable(level);
 start=(uint32_t)rt_tick_get_millisecond();
 while(*used<target&&(uint32_t)((uint32_t)rt_tick_get_millisecond()-start)<deadline_ms) {
  size_t count=target-*used;rt_ssize_t n;
  if(count>1024)count=1024;
  n=rt_device_read(mic,0,pcm+*used,count);
  if(n<0||(size_t)n>count)goto done;
  if(n>0)*used+=(size_t)n;else rt_thread_mdelay(2);
 }
 if(*used==target)result=0;
 done:level=rt_hw_interrupt_disable();audio->record->pipe.flag=saved_flags;rt_hw_interrupt_enable(level);
 return result;
}
#endif
