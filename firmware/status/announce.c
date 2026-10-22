#include <rtthread.h>
#include "announce.h"
#ifdef WATCH_VOICE_ENABLED
#include <rtthread.h>
#include <rtdevice.h>
#include <board.h>
#include <string.h>
#include "announce_protocol.h"
#include "alert_audio.h"
#define SPEAKER_PIN GET_PIN(21,6)
static unsigned audio_owner;
static struct watch_announce_policy policy;
static struct rt_semaphore wake;
static int initialized;
static struct rt_audio_device *sound;
static int sound_fault;
int watch_audio_claim(unsigned owner) {
 rt_base_t level=rt_hw_interrupt_disable();int ok=!audio_owner;
 if(ok)audio_owner=owner;
 rt_hw_interrupt_enable(level);return ok;
}
void watch_audio_release(unsigned owner) {
 rt_base_t level=rt_hw_interrupt_disable();if(audio_owner==owner)audio_owner=0;rt_hw_interrupt_enable(level);
}
/* The pinned sound0 driver waits forever in generic write/close, and its
 * playback thread waits for a next queue item at end of stream. Keep sound0
 * open for device lifetime, enqueue with finite pool waits, and end with
 * silence. No repeat init of the shared TDM/PDM clocks or unbounded close. */
static int output_block(const int16_t *pcm) {
 unsigned char *block=rt_mp_alloc(sound->replay->mp,rt_tick_from_millisecond(200));
 if(!block)return -1;
 memcpy(block,pcm,RT_AUDIO_REPLAY_MP_BLOCK_SIZE);
 if(rt_data_queue_push(&sound->replay->queue,block,RT_AUDIO_REPLAY_MP_BLOCK_SIZE,RT_WAITING_NO)!=RT_EOK){rt_mp_free(block);return -1;}
 if(!sound->replay->activated) {
  int stream=AUDIO_STREAM_REPLAY;
  if(rt_device_control((rt_device_t)sound,AUDIO_CTL_START,&stream)!=RT_EOK)return -1;
 }
 return 0;
}
static int play(void) {
 struct rt_audio_caps caps;size_t i=0,k;int16_t pcm[RT_AUDIO_REPLAY_MP_BLOCK_SIZE/2];
 uint32_t start=rt_tick_get_millisecond();int result=-1;
 if(sound_fault)return -1;
 if(!sound) {
  rt_device_t dev=rt_device_find("sound0");
  if(!dev||rt_device_open(dev,RT_DEVICE_OFLAG_WRONLY)!=RT_EOK)return -1;
  sound=(struct rt_audio_device*)dev;
  memset(&caps,0,sizeof(caps));
  caps.main_type=AUDIO_TYPE_MIXER;caps.sub_type=AUDIO_MIXER_VOLUME;caps.udata.value=60;
  if(rt_device_control(dev,AUDIO_CTL_CONFIGURE,&caps)!=RT_EOK)goto done;
 }
 memset(&caps,0,sizeof(caps));caps.main_type=AUDIO_TYPE_OUTPUT;caps.sub_type=AUDIO_DSP_PARAM;
 caps.udata.config.samplerate=16000;caps.udata.config.channels=1;caps.udata.config.samplebits=16;
 if(rt_device_control((rt_device_t)sound,AUDIO_CTL_CONFIGURE,&caps)!=RT_EOK)goto done;
 rt_pin_write(SPEAKER_PIN,PIN_HIGH);
 while(i<sizeof(watch_alert_audio)) {
  if((uint32_t)(rt_tick_get_millisecond()-start)>7000u)goto done;
  memset(pcm,0,sizeof(pcm));
  for(k=0;k<sizeof(pcm)/sizeof(pcm[0])&&i<sizeof(watch_alert_audio);k+=2,i++)
   pcm[k]=pcm[k+1]=watch_mulaw_decode(watch_alert_audio[i]);
  if(output_block(pcm))goto done;
 }
 memset(pcm,0,sizeof(pcm));if(output_block(pcm)||output_block(pcm))goto done;
 /* The BSP consumes 2048-byte periods. Two extra silent periods cover its
  * pending DMA buffers. Wait for bounded queue drain, then their output. */
 while(!sound->replay->queue.is_empty) {
  if((uint32_t)(rt_tick_get_millisecond()-start)>7000u)goto done;
  rt_thread_mdelay(5);
 }
 rt_thread_mdelay(200);result=0;
 done:
 rt_pin_write(SPEAKER_PIN,PIN_LOW);
 /* PDM's fixed divider depends on the original boot TDM clock. Mono
  * playback changes that clock; restore boot stereo/16k before mic owns it. */
 memset(&caps,0,sizeof(caps));caps.main_type=AUDIO_TYPE_OUTPUT;caps.sub_type=AUDIO_DSP_PARAM;
 caps.udata.config.samplerate=16000;caps.udata.config.channels=2;caps.udata.config.samplebits=16;
 if(rt_device_control((rt_device_t)sound,AUDIO_CTL_CONFIGURE,&caps)!=RT_EOK)result=-1;
 if(result)sound_fault=1;
 return result;
}
static void worker(void *unused) {
 (void)unused;
 for(;;) {
  unsigned start;int owned=0,result=-1;char id[33];
  rt_sem_take(&wake,RT_WAITING_FOREVER);strcpy(id,policy.last);start=rt_tick_get_millisecond();
  while((uint32_t)(rt_tick_get_millisecond()-start)<10000u) {
   if(watch_audio_claim(2)){owned=1;break;}rt_thread_mdelay(20);
  }
  if(owned){rt_kprintf("WATCH ANNOUNCE PLAY %s\n",id);result=play();watch_audio_release(2);}
  {rt_base_t level=rt_hw_interrupt_disable();watch_announce_finish(&policy);rt_hw_interrupt_enable(level);}
  rt_kprintf("WATCH ANNOUNCE %s %s\n",result?"FAILED":"DONE",id);
 }
}
static int watch_announce(int argc,char **argv) {
 int r;rt_base_t level;
 if(argc!=2||!initialized){rt_kprintf("WATCH ANNOUNCE NACK unavailable\n");return -1;}
 level=rt_hw_interrupt_disable();r=watch_announce_request(&policy,argv[1]);rt_hw_interrupt_enable(level);
 if(r<0){rt_kprintf("WATCH ANNOUNCE NACK %d\n",r);return r;}
 rt_kprintf("WATCH ANNOUNCE ACK %s %s\n",argv[1],r?"duplicate":"queued");
 if(!r)rt_sem_release(&wake);
 return 0;
}
MSH_CMD_EXPORT(watch_announce, bounded fixed Chinese event announcement with deduplication);
int watch_announce_init(void) {
 rt_thread_t thread;rt_sem_init(&wake,"announce",0,RT_IPC_FLAG_FIFO);
 thread=rt_thread_create("announce",worker,RT_NULL,6144,23,10);
 if(!thread)return -1;
 initialized=1;rt_thread_startup(thread);return 0;
}
#else
int watch_audio_claim(unsigned owner){(void)owner;return 1;}
void watch_audio_release(unsigned owner){(void)owner;}
int watch_announce_init(void){return 0;}
#endif
