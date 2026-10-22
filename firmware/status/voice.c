#include "voice.h"
#include <rtthread.h>
#include <rtdevice.h>
#include <board.h>
#include <string.h>
#include <stdlib.h>
#include "voice_protocol.h"
#include "voice_capture.h"
#include "announce.h"
#ifdef WATCH_VOICE_ENABLED
#include <wlan_mgnt.h>
#include <lwip/sockets.h>
#include <lwip/inet.h>
static char host[16],token[65],status[16]="READY",last_action[8];
static unsigned port,seconds_to_record,request_count;
static int busy,http_result;
static unsigned recorded_bytes;
static unsigned char pcm[256000] __attribute__((section(".m33_m55_shared_hyperram"),aligned(32)));
static uint32_t now(void){return (uint32_t)rt_tick_get_millisecond();}
static void set_status(const char *s,const char *a) {
 rt_base_t level=rt_hw_interrupt_disable();
 strcpy(status,s);strcpy(last_action,a?a:"");rt_hw_interrupt_enable(level);
 watch_voice_redraw();
}
void watch_voice_snapshot(char s[16],char a[8]) {
 rt_base_t level=rt_hw_interrupt_disable();strcpy(s,status);strcpy(a,last_action);rt_hw_interrupt_enable(level);
}
static int transport_error;
static int wait_socket(int fd,int write,uint32_t start) {
 while((uint32_t)(now()-start)<120000u) {
  fd_set set;struct timeval timeout={0,200000};int r;FD_ZERO(&set);FD_SET(fd,&set);
  r=lwip_select(fd+1,write?NULL:&set,write?&set:NULL,NULL,&timeout);
  if(r>0)return 0;
  if(r<0){transport_error=errno;return -1;}
 }
 transport_error=-2;return -1;
}
static int send_all(int fd,const unsigned char *data,size_t length,uint32_t start) {
 while(length) {int n;if(wait_socket(fd,1,start))return -1;n=lwip_send(fd,data,length>4096?4096:length,0);if(n<=0){transport_error=n<0?errno:0;return -1;}data+=n;length-=n;}return 0;
}
static int upload(size_t length,char action[8]) {
 char header[512],response[1024]={0},request[65];struct sockaddr_in address;
 const char *stage="header-config";int code;
 unsigned long nonblocking=1;int fd=-1,result=-1,error=0;socklen_t error_len=sizeof(error);size_t used=0;uint32_t start=now();
 transport_error=-1;
 /* TRNG-free request uniqueness: hardware tick plus monotonic counter and boot entropy. */
 rt_snprintf(request,sizeof(request),"v%08x-%08x-%u",(unsigned)SysTick->VAL,(unsigned)start,++request_count);
 if(watch_voice_header(header,sizeof(header),host,port,token,request,length))goto done;
 stage="socket";fd=lwip_socket(AF_INET,SOCK_STREAM,0);if(fd<0){transport_error=errno;goto done;}
 stage="ioctl";if(lwip_ioctl(fd,FIONBIO,&nonblocking)){transport_error=errno;goto done;}
 memset(&address,0,sizeof(address));address.sin_family=AF_INET;address.sin_port=htons(port);address.sin_addr.s_addr=inet_addr(host);
 (void)lwip_connect(fd,(struct sockaddr*)&address,sizeof(address));
 stage="connect-wait";if(wait_socket(fd,1,start))goto done;
 stage="SO_ERROR";if(lwip_getsockopt(fd,SOL_SOCKET,SO_ERROR,&error,&error_len)){transport_error=errno;goto done;}
 if(error){transport_error=error;goto done;}
 stage="header-send";if(send_all(fd,(const unsigned char*)header,strlen(header),start))goto done;
 stage="body-send";if(send_all(fd,pcm,length,start))goto done;
 while(used<sizeof(response)-1) {
  int n;stage="read-wait";if(wait_socket(fd,0,start))goto done;
  stage="read";n=lwip_recv(fd,response+used,sizeof(response)-used-1,0);
  if(n<=0){transport_error=n<0?errno:0;break;}
  used+=n;response[used]=0;if(!watch_voice_parse(response,action)){result=0;break;}
 }
 done:
 if(result) {
  code=watch_voice_http_code(response);
  if(code&&(code!=200||(!strcmp(stage,"read")&&transport_error==0))){stage="HTTP-reject";transport_error=code;}
  rt_kprintf("WATCH VOICE TRANSPORT stage=%s err=%d\n",stage,transport_error);
 }
 if(fd>=0)lwip_close(fd);
 return result;
}
static void record_thread(void *unused) {
 rt_device_t mic=NULL;struct rt_audio_caps caps;size_t used=0,target=seconds_to_record*32000u;int failed=1,opened=0,audio_owned=1;char action[8]="";
 (void)unused;
 set_status("LISTENING",NULL);
 mic=rt_device_find("mic0");if(!mic)goto done;
 /* PDM shares the TDM clock. Official sound0 registration initializes TDM
  * once at boot (rt_audio_register -> rt_device_init -> sound_init). Do not
  * reinitialize it here after PDM has registered and configured its IRQ. */
 if(rt_device_open(mic,RT_DEVICE_OFLAG_RDONLY)!=RT_EOK)goto done;
 opened=1;
 memset(&caps,0,sizeof(caps));caps.main_type=AUDIO_TYPE_INPUT;caps.sub_type=AUDIO_DSP_PARAM;
 caps.udata.config.samplerate=16000;caps.udata.config.channels=1;caps.udata.config.samplebits=16;
 if(rt_device_control(mic,AUDIO_CTL_CONFIGURE,&caps)!=RT_EOK)goto done;
 caps.main_type=AUDIO_TYPE_MIXER;caps.sub_type=AUDIO_MIXER_VOLUME;caps.udata.value=15;
 if(rt_device_control(mic,AUDIO_CTL_CONFIGURE,&caps)!=RT_EOK)goto done;
 if(watch_voice_record(mic,pcm,target,seconds_to_record*1000u+2000u,&used))goto done;
 rt_device_close(mic);opened=0;watch_audio_release(1);audio_owned=0;
 if(used!=target)goto done;
 rt_kprintf("WATCH VOICE AUDIO bytes=%u rate=16000 channels=1 bits=16\n",(unsigned)used);
 {rt_base_t level=rt_hw_interrupt_disable();recorded_bytes=(unsigned)used;http_result=-1;rt_hw_interrupt_enable(level);}
 set_status("RECOGNIZING",NULL);
 if(!rt_wlan_is_ready()||upload(used,action))goto done;
 failed=0;
 done:if(opened)rt_device_close(mic);if(audio_owned)watch_audio_release(1);
 {rt_base_t level=rt_hw_interrupt_disable();recorded_bytes=(unsigned)used;if(!failed)http_result=1;rt_hw_interrupt_enable(level);}
 set_status(failed?"FAILED":"DONE",failed?NULL:action);
 {rt_base_t level=rt_hw_interrupt_disable();busy=0;rt_hw_interrupt_enable(level);}
 rt_kprintf("WATCH VOICE %s action=%s bytes=%u\n",failed?"FAILED":"DONE",failed?"none":action,(unsigned)used);
}
int watch_voice_begin(unsigned seconds) {
 rt_thread_t thread;rt_base_t level;
 if(seconds<1||seconds>8)return -1;
 level=rt_hw_interrupt_disable();if(busy){rt_hw_interrupt_enable(level);return -1;}
 if(!port||!rt_wlan_is_ready()||!rt_device_find("mic0")){strcpy(status,"FAILED");last_action[0]=0;rt_hw_interrupt_enable(level);return -1;}
 if(!watch_audio_claim(1)){rt_hw_interrupt_enable(level);return -1;}
 busy=1;recorded_bytes=0;http_result=0;seconds_to_record=seconds;rt_hw_interrupt_enable(level);
 thread=rt_thread_create("watch_voice",record_thread,NULL,8192,22,10);
 if(!thread){level=rt_hw_interrupt_disable();busy=0;watch_audio_release(1);strcpy(status,"FAILED");rt_hw_interrupt_enable(level);return -1;}
 rt_thread_startup(thread);return 0;
}
static int watch_voice_gateway(int argc,char **argv) {
 char header[512],*end;unsigned value;unsigned long parsed;rt_base_t level;
 if(argc!=4)return -1;
 parsed=strtoul(argv[2],&end,10);if(!*argv[2]||*end||!parsed||parsed>65535)return -1;value=(unsigned)parsed;
 if(watch_voice_header(header,sizeof(header),argv[1],value,argv[3],"validate",32000))return -1;
 level=rt_hw_interrupt_disable();if(busy){rt_hw_interrupt_enable(level);return -1;}
 strcpy(host,argv[1]);strcpy(token,argv[3]);port=value;rt_hw_interrupt_enable(level);
 rt_kprintf("WATCH VOICE GATEWAY ACK token=RAM_only\n");return 0;
}
MSH_CMD_EXPORT(watch_voice_gateway, configure voice IPv4 port token without echo);
static int watch_voice(int argc,char **argv) {
 unsigned seconds=6;int r;if(argc>2)return -1;if(argc==2){char *end;unsigned long value=strtoul(argv[1],&end,10);if(!*argv[1]||*end||value>8)return -1;seconds=(unsigned)value;}
 r=watch_voice_begin(seconds);watch_voice_redraw();rt_kprintf("WATCH VOICE %s bounded=1\n",r?"NACK":"ACK");return r;
}
MSH_CMD_EXPORT(watch_voice, record bounded 1 to 8 seconds default 6 and execute voice command);
static int watch_voice_info(void) {
 char s[16],a[8];unsigned b,c,bytes;int http;rt_base_t level=rt_hw_interrupt_disable();
 strcpy(s,status);strcpy(a,last_action);b=(unsigned)busy;c=(unsigned)(port!=0);bytes=recorded_bytes;http=http_result;rt_hw_interrupt_enable(level);
 rt_kprintf("WATCH VOICE INFO status=%s action=%s busy=%u configured=%u bytes=%u http=%s\n",s,*a?a:"none",b,c,bytes,http>0?"ok":http<0?"error_or_pending":"none");return 0;
}
MSH_CMD_EXPORT(watch_voice_info, report voice state without credentials);
#else
void watch_voice_snapshot(char s[16],char a[8]) {strcpy(s,"");a[0]=0;}
int watch_voice_begin(unsigned seconds){(void)seconds;return -1;}
#endif
