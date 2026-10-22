#include "standalone.h"
#include <rtthread.h>
#ifdef WATCH_NETWORK_ENABLED
#include <rtthread.h>
#include <rtdevice.h>
#include <stdlib.h>
#include <string.h>
#include <lwip/sockets.h>
#include <lwip/inet.h>
#include <wlan_mgnt.h>
#include "usbh_uvc_stream.h"
#include "gateway.h"
static char gateway_host[16],gateway_token[65],session_seed[33],session_id[64];
static unsigned run_id;
static unsigned gateway_port,run_seconds,run_interval,run_calls;
static volatile int running,stopping;
static uint32_t started;
static struct usbh_videoframe pool[2];
static unsigned char buffers[2][320*240*2] __attribute__((section(".m33_m55_shared_hyperram"),aligned(32)));
static uint32_t clock_ms(void) { return (uint32_t)rt_tick_get_millisecond(); }
static int remaining(void) { return watch_gateway_budget(clock_ms(),started,run_seconds,0,1,stopping); }
int watch_standalone_running(void){return running;}
void watch_standalone_stop(void){stopping=1;}
int watch_standalone_cancelled(void){return running&&stopping;}
static int wait_socket(int fd,int writing,uint32_t begin) {
 while(remaining()&&(uint32_t)(clock_ms()-begin)<30000) {
  fd_set set;struct timeval timeout={0,200000};int r;
  FD_ZERO(&set);FD_SET(fd,&set);
  r=lwip_select(fd+1,writing?NULL:&set,writing?&set:NULL,NULL,&timeout);
  if(r>0)return 0;
  if(r<0)return -1;
 }
 return -1;
}
static int send_bytes(int fd,const unsigned char *data,size_t size,uint32_t begin) {
 while(size) {
  int n;if(wait_socket(fd,1,begin))return -1;
  n=lwip_send(fd,data,size>4096?4096:size,0);if(n<=0)return -1;
  data+=n;size-=(size_t)n;
 }
 return 0;
}
static int upload(struct usbh_videoframe *frame,struct watch_reply *reply,unsigned call) {
 struct sockaddr_in address;int fd=-1,r=-1,error=0;unsigned long nonblocking=1;
 socklen_t error_size=sizeof(error);char header[640],response[1024];size_t length=0;uint32_t begin=clock_ms();
 if(watch_gateway_header(header,sizeof(header),gateway_host,gateway_port,gateway_token,watch_local_task_id(),session_id,clock_ms(),call==1))return -1;
 fd=lwip_socket(AF_INET,SOCK_STREAM,0);if(fd<0)return -1;
 if(lwip_ioctl(fd,FIONBIO,&nonblocking))goto done;
 memset(&address,0,sizeof(address));address.sin_family=AF_INET;address.sin_port=htons(gateway_port);address.sin_addr.s_addr=inet_addr(gateway_host);
 (void)lwip_connect(fd,(struct sockaddr*)&address,sizeof(address));
 if(wait_socket(fd,1,begin)||lwip_getsockopt(fd,SOL_SOCKET,SO_ERROR,&error,&error_size)||error)goto done;
 if(send_bytes(fd,(const unsigned char*)header,strlen(header),begin)||send_bytes(fd,frame->frame_buf,frame->frame_size,begin))goto done;
 while(length<sizeof(response)-1&&remaining()) {
  int n;if(wait_socket(fd,0,begin))goto done;
  n=lwip_recv(fd,response+length,sizeof(response)-1-length,0);if(n<0)goto done;if(!n)break;
  length+=(size_t)n;response[length]=0;
  /* Gateway compact body is newline terminated and not chunk encoded. */
  if(!watch_gateway_parse(response,reply)){r=0;break;}
 }
 done: if(fd>=0)lwip_close(fd);return r;
}
static void run_thread(void *unused) {
 unsigned calls=0,i;int failed=0;(void)unused;
 for(i=0;i<2;i++){pool[i].frame_buf=buffers[i];pool[i].frame_bufsize=sizeof(buffers[i]);}
 if(usbh_video_stream_create(pool,2)<0){failed=1;goto done;}
 usbh_video_stream_start(320,240,USBH_VIDEO_FORMAT_UNCOMPRESSED);
 while(watch_gateway_budget(clock_ms(),started,run_seconds,calls,run_calls,stopping)) {
  struct usbh_videoframe *frame=NULL,*latest=NULL;struct watch_reply reply;int r;
  if(!rt_wlan_is_ready()){failed=1;break;}
  if(usbh_video_stream_dequeue(&frame,RT_TICK_PER_SECOND)!=0) {failed=1;break;}
  /* Drain stale queued frames so each observation uses the newest capture. */
  while(usbh_video_stream_dequeue(&latest,0)==0){usbh_video_stream_enqueue(frame);frame=latest;}
  if(frame->frame_size!=sizeof(buffers[0])){usbh_video_stream_enqueue(frame);failed=1;break;}
  calls++;r=upload(frame,&reply,calls);usbh_video_stream_enqueue(frame);
  if(r||!remaining()){failed=1;break;}
  watch_local_result(reply.status,reply.event_count,1);
  rt_kprintf("WATCH RUN decision=%u status=%s count=%u\n",calls,reply.status,(unsigned)reply.event_count);
  if(!strcmp(reply.status,"paused"))break;
  for(i=0;i<run_interval*10&&remaining();i++)rt_thread_mdelay(100);
 }
 usbh_video_stream_stop();
 done: watch_local_result("paused",0,0);running=0;
 rt_kprintf("WATCH RUN stopped calls=%u reason=%s\n",calls,failed?"error_or_deadline":"stopped_or_budget");
}
static int watch_gateway(int argc,char **argv) {
 char header[640];unsigned port;
 if(running||argc!=5)return -1;
 port=(unsigned)atoi(argv[2]);
 if(watch_gateway_header(header,sizeof(header),argv[1],port,argv[3],1,argv[4],0,1)||strlen(argv[4])>32) {rt_kprintf("WATCH GATEWAY NACK\n");return -1;}
 strcpy(gateway_host,argv[1]);strcpy(gateway_token,argv[3]);gateway_port=port;strcpy(session_seed,argv[4]);run_id=0;
 rt_kprintf("WATCH GATEWAY ACK transport=HTTP_LAN token=RAM_only\n");return 0;
}
MSH_CMD_EXPORT(watch_gateway, configure IPv4 port runtime token session seed for LAN gateway);
static int watch_run(int argc,char **argv) {
 rt_thread_t thread;unsigned seconds,interval,calls;
 if(argc!=4||running||!gateway_port||!watch_local_task_id()||!rt_wlan_is_ready()||!usbh_find_class_instance("/dev/video0")){rt_kprintf("WATCH RUN NACK not_ready\n");return -1;}
 seconds=(unsigned)atoi(argv[1]);interval=(unsigned)atoi(argv[2]);calls=(unsigned)atoi(argv[3]);
 if(!seconds||seconds>86400||interval<5||interval>3600||!calls||calls>1000)return -1;
 rt_snprintf(session_id,sizeof(session_id),"%s_%u",session_seed,++run_id);
 run_seconds=seconds;run_interval=interval;run_calls=calls;started=clock_ms();stopping=0;running=1;
 watch_local_result("idle",0,0);
 thread=rt_thread_create("watch_net",run_thread,NULL,8192,23,10);
 if(!thread){running=0;watch_local_result("paused",0,0);return -1;}
 rt_thread_startup(thread);rt_kprintf("WATCH RUN ACK bounded=1\n");return 0;
}
MSH_CMD_EXPORT(watch_run, bounded seconds interval maxcalls board capture and gateway loop);
static int watch_stop(void){watch_standalone_stop();rt_kprintf("WATCH STOP requested\n");return 0;}
MSH_CMD_EXPORT(watch_stop, cancel board camera gateway loop);
#else
int watch_standalone_running(void){return 0;}
void watch_standalone_stop(void){}
int watch_standalone_cancelled(void){return 0;}
#endif
