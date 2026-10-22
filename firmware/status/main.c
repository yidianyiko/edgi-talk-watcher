#include <rtthread.h>
#include <rtdevice.h>
#include <board.h>
#include "usbh_core.h"
#include "status.h"
#include "product.h"
#include "standalone.h"
#include "voice.h"
#include "announce.h"
#include "face.h"
#include "drv_touch.h"
#include "usbh_uvc_stream.h"
#include "camera_recovery.h"

#ifdef WATCH_NETWORK_ENABLED
#include <wlan_mgnt.h>
#ifdef WATCH_VOICE_ENABLED
#define WATCH_BUILD "watch-product-voice-20261022-10"
#else
#define WATCH_BUILD "watch-product-net-20261020-4"
#endif
#else
#define WATCH_BUILD "watch-product-20261020-4"
#endif
static struct watch_state state;
static struct watch_product product;
static rt_device_t touch;
static struct rt_mutex lock;
static rt_device_t lcd;
static struct rt_device_graphic_info info;
static unsigned frame_hash;
static unsigned face_key;
/* 5x7 uppercase bitmap glyphs, column major. */
static const unsigned char letters[26][5] = {
 {0x7e,0x11,0x11,0x11,0x7e},{0x7f,0x49,0x49,0x49,0x36},
 {0x3e,0x41,0x41,0x41,0x22},{0x7f,0x41,0x41,0x22,0x1c},
 {0x7f,0x49,0x49,0x49,0x41},{0x7f,9,9,9,1},
 {0x3e,0x41,0x49,0x49,0x7a},{0x7f,8,8,8,0x7f},
 {0,0x41,0x7f,0x41,0},{0x20,0x40,0x41,0x3f,1},
 {0x7f,8,0x14,0x22,0x41},{0x7f,0x40,0x40,0x40,0x40},
 {0x7f,2,0x0c,2,0x7f},{0x7f,4,8,0x10,0x7f},
 {0x3e,0x41,0x41,0x41,0x3e},{0x7f,9,9,9,6},
 {0x3e,0x41,0x51,0x21,0x5e},{0x7f,9,0x19,0x29,0x46},
 {0x46,0x49,0x49,0x49,0x31},{1,1,0x7f,1,1},
 {0x3f,0x40,0x40,0x40,0x3f},{0x1f,0x20,0x40,0x20,0x1f},
 {0x3f,0x40,0x38,0x40,0x3f},{0x63,0x14,8,0x14,0x63},
 {7,8,0x70,8,7},{0x61,0x51,0x49,0x45,0x43}
};
static const unsigned char digits[10][5] = {
 {0x3e,0x51,0x49,0x45,0x3e},{0,0x42,0x7f,0x40,0},
 {0x42,0x61,0x51,0x49,0x46},{0x21,0x41,0x45,0x4b,0x31},
 {0x18,0x14,0x12,0x7f,0x10},{0x27,0x45,0x45,0x45,0x39},
 {0x3c,0x4a,0x49,0x49,0x30},{1,0x71,9,5,3},
 {0x36,0x49,0x49,0x49,0x36},{6,0x49,0x49,0x29,0x1e}
};
static void fill(int x, int y, int w, int h, unsigned short color) {
    int row, col;
    for (row = y; row < y+h && row < info.height; row++) {
        unsigned short *pixels = (unsigned short *)(info.framebuffer + row * info.pitch);
        for (col = x; col < x+w && col < info.width; col++) pixels[col] = color;
    }
}
static void text(int x, int y, const char *str, int scale, unsigned short color) {
    for (; *str; str++, x += scale * 6) {
        char c = *str;
        const unsigned char *glyph = RT_NULL;
        int col, row;
        if (c >= 'a' && c <= 'z') c -= 32;
        if (c >= 'A' && c <= 'Z') glyph = letters[c-'A'];
        if (c >= '0' && c <= '9') glyph = digits[c-'0'];
        if (!glyph) continue;
        for (col=0; col<5; col++) for (row=0; row<7; row++)
            if (glyph[col] & (1<<row)) fill(x+col*scale,y+row*scale,scale,scale,color);
    }
}
static void face_rect(int x,int y,int w,int h,unsigned short color,void *context) {
    (void)context;fill(x,y,w,h,color);
}
static int render(void) {
    static const unsigned short colors[] = {0x8410,0x051f,0x07e0,0xf800,0xfd20,0xffe0};
    const char *name = watch_name(state.status);
    char seq[32];
    char voice[16]="",action[8]="";
    struct watch_face face;
    unsigned i, h = 2166136261u;
    if (!lcd) return -1;
#ifdef WATCH_VOICE_ENABLED
    watch_voice_snapshot(voice,action);
#endif
    face=watch_face_pose(state.status,voice,(uint32_t)rt_tick_get_millisecond());
    fill(0,0,info.width,info.height,0x0841);
    fill(0,0,info.width,24,colors[state.status]);
    text(24,64,"VISUAL WATCHER",4,0xffff);
    watch_face_draw(info.width,info.height,face,face_rect,RT_NULL);
    text(24,info.height*55/100,name,4,colors[state.status]);
    text(16,info.height*2/3,product.task_label,2,0xffff);
    rt_snprintf(seq,sizeof(seq),"TASK %u EVENTS %u",(unsigned)product.task_id,(unsigned)product.event_count);
    text(16,info.height*2/3+24,seq,2,0xffff);
    text(8,info.height-32,"START PAUSE NEXT HISTORY",2,0xffff);
#ifdef WATCH_VOICE_ENABLED
    text(16,110,voice,3,0xffe0);text(280,110,action,2,0xffff);
    text(8,info.height-60,"SPEAK",2,0xffe0);
#endif
    rt_snprintf(seq,sizeof(seq),"SEQ %u",(unsigned)state.sequence);
    text(24,info.height*2/3+48,seq,3,0xffff);
    for (i=0; i<info.pitch*info.height; i++) h=(h^info.framebuffer[i])*16777619u;
    if (rt_device_control(lcd,RTGRAPHIC_CTRL_RECT_UPDATE,RT_NULL) != RT_EOK) return -1;
    frame_hash = h;
    face_key=watch_face_key(face);
    return 0;
}
void watch_voice_redraw(void) { rt_mutex_take(&lock,RT_WAITING_FOREVER);render();rt_mutex_release(&lock); }
static uint32_t now_ms(void) { return (uint32_t)rt_tick_get_millisecond(); }
static int watch_status(int argc, char **argv) {
    struct watch_state next;
    int result;
    if (argc != 3) { rt_kprintf("WATCH NACK usage\n"); return -1; }
    rt_mutex_take(&lock,RT_WAITING_FOREVER);
    next = state;
    result = watch_apply(&next,argv[1],argv[2],now_ms());
    if (!result) {
        watch_standalone_stop();
        struct watch_state old = state;
        state = next;
        if (render()) { state=old; result=-3; }
    }
    if (result) rt_kprintf("WATCH NACK %d\n",result);
    else rt_kprintf("WATCH ACK %u %s %08x\n",(unsigned)state.sequence,watch_name(state.status),frame_hash);
    rt_mutex_release(&lock);
    return result;
}
MSH_CMD_EXPORT(watch_status, set serial watcher status);
#ifdef WATCH_VOICE_ENABLED
static int watch_camera_reset(void) {
    int result=watch_camera_recover(watch_standalone_running(),USBHS_BASE);
    if(result)rt_kprintf("WATCH CAMERA RESET NACK %d\n",result);
    else rt_kprintf("WATCH CAMERA RESET ACK ready=1\n");
    return result;
}
MSH_CMD_EXPORT(watch_camera_reset, bounded USB host restart while camera worker stopped);
#endif
static int watch_info(void) {
    rt_mutex_take(&lock,RT_WAITING_FOREVER);
    rt_kprintf("WATCH INFO %s %u %s %08x %ux%u pitch=%u fb=%08x\n",WATCH_BUILD,
        (unsigned)state.sequence,watch_name(state.status),frame_hash,info.width,info.height,info.pitch,(unsigned)info.framebuffer);
    rt_mutex_release(&lock);
    return 0;
}
MSH_CMD_EXPORT(watch_info, read watcher screen state);
static int watch_task(int argc,char **argv) {
    if(watch_standalone_running()) { rt_kprintf("WATCH TASK NACK busy\n"); return -1; }
    int r=-1;
    rt_mutex_take(&lock,RT_WAITING_FOREVER);
    if(argc==3) r=watch_product_task(&product,argv[1],argv[2]);
    if(!r) { watch_pause(&state,now_ms()); r=render(); }
    rt_kprintf("WATCH TASK %s %u %s\n",r?"NACK":"ACK",(unsigned)product.task_id,product.task_label);
    rt_mutex_release(&lock); return r;
}
MSH_CMD_EXPORT(watch_task, set task id and ASCII label);
static int watch_count(int argc,char **argv) {
    int r=-1;
    rt_mutex_take(&lock,RT_WAITING_FOREVER);
    if(argc==2) r=watch_product_count(&product,argv[1]);
    if(!r) r=render();
    rt_kprintf("WATCH COUNT %s %u\n",r?"NACK":"ACK",(unsigned)product.event_count);
    rt_mutex_release(&lock); return r;
}
MSH_CMD_EXPORT(watch_count, set host persisted event count);
static int request_action(const char *action) {
    if(!rt_strcmp(action,"pause")||!rt_strcmp(action,"next")) watch_standalone_stop();
    int r=watch_product_action(&product,action);
    if(!r) {
        /* A request is not proof that the host started capture. */
        if(!rt_strcmp(action,"pause")||!rt_strcmp(action,"next")) watch_pause(&state,now_ms());
        render();
        rt_kprintf("WATCH ACTION %u %s\n",(unsigned)product.request_id,product.action);
    } else rt_kprintf("WATCH ACTION NACK\n");
    return r;
}
static int watch_action(int argc,char **argv) {
    int r=-1; rt_mutex_take(&lock,RT_WAITING_FOREVER);
    if(argc==2) r=request_action(argv[1]);
    rt_mutex_release(&lock); return r;
}
MSH_CMD_EXPORT(watch_action, request start pause next history from host);
static int watch_control(void) {
    rt_mutex_take(&lock,RT_WAITING_FOREVER);
    rt_kprintf("WATCH CONTROL %u %s\n",(unsigned)product.request_id,product.action);
    rt_mutex_release(&lock); return 0;
}
MSH_CMD_EXPORT(watch_control, poll last user request);
static int watch_probe(void) {
    rt_kprintf("WATCH CAP uvc=%s touch=%s wlan=%s audio=%s mic=%s network_stack=see_watch_network\n",
        usbh_find_class_instance("/dev/video0")?"connected":"absent",
        touch?"registered":"absent",rt_device_find("wlan0")?"registered":"absent",
        rt_device_find("sound0")?"registered":"absent",rt_device_find("mic0")?"registered":"absent");
    return 0;
}
MSH_CMD_EXPORT(watch_probe, report devices without opening camera or network);
static int watch_capture(int argc,char **argv) {
    if(watch_standalone_running()) { rt_kprintf("WATCH CAPTURE NACK busy\n"); return -1; }
    /* Bounded single frame: never takes LCD ownership or starts a background camera. */
    static struct usbh_videoframe pool[2];
    static unsigned char buffers[2][320*240*2] __attribute__((section(".m33_m55_shared_hyperram"),aligned(32)));
    struct usbh_videoframe *f=RT_NULL; unsigned i,h=2166136261u; int r;
    (void)argc; (void)argv;
    if(!usbh_find_class_instance("/dev/video0")) { rt_kprintf("WATCH CAPTURE NACK no_uvc_device\n"); return -1; }
    for(i=0;i<2;i++) { pool[i].frame_buf=buffers[i]; pool[i].frame_bufsize=sizeof(buffers[i]); }
    r=usbh_video_stream_create(pool,2);
    if(r<0) { rt_kprintf("WATCH CAPTURE NACK pool=%d\n",r); return r; }
    usbh_video_stream_start(320,240,USBH_VIDEO_FORMAT_UNCOMPRESSED);
    r=usbh_video_stream_dequeue(&f,2*RT_TICK_PER_SECOND);
    if(!r&&f&&f->frame_size<=sizeof(buffers[0])) {
        for(i=0;i<f->frame_size;i++) h=(h^f->frame_buf[i])*16777619u;
        rt_kprintf("WATCH CAPTURE ACK bytes=%u hash=%08x format=yuyv width=320 height=240\n",(unsigned)f->frame_size,h);
        usbh_video_stream_enqueue(f);
    } else { rt_kprintf("WATCH CAPTURE NACK timeout_or_size=%d\n",r); r=-1; }
    usbh_video_stream_stop(); return r;
}
MSH_CMD_EXPORT(watch_capture, bounded board USB camera single frame test);
static int watch_network(void) {
#ifdef WATCH_NETWORK_ENABLED
    rt_kprintf("WATCH NETWORK driver=%s connected=%u ready=%u transport=board_SDIO resources=in_image auto_join=disabled\n",rt_device_find("wlan0")?"registered":"absent",(unsigned)rt_wlan_is_connected(),(unsigned)rt_wlan_is_ready());
    return rt_wlan_is_ready()?0:-1;
#else
    rt_kprintf("WATCH NETWORK unavailable reason=wifi_driver_and_lwip_not_enabled required=CYW55513_SDIO_WHD_resources_and_network_configuration\n"); return -1;
#endif
}
MSH_CMD_EXPORT(watch_network, report network readiness without credentials);
static void poll_touch(void) {
    struct rt_touch_data points[5]; unsigned i;
    if(!touch) return;
    rt_memset(points,0,sizeof(points));
    if(rt_device_read(touch,0,points,5)<=0) return;
    for(i=0;i<5;i++) if(points[i].event==RT_TOUCH_EVENT_DOWN && points[i].y_coordinate>=info.height-60 && points[i].x_coordinate<info.width) {
#ifdef WATCH_VOICE_ENABLED
        if(points[i].y_coordinate<info.height-34) {watch_voice_begin(6);render();break;}
#endif
        const char *actions[]={"start","pause","next","history"};
        request_action(actions[points[i].x_coordinate*4/info.width]); break;
    }
}
uint32_t watch_local_task_id(void) { return product.task_id; }
void watch_local_result(const char *status,uint32_t count,int update_count) {
    enum watch_status value;
    rt_mutex_take(&lock,RT_WAITING_FOREVER);
    if(watch_standalone_cancelled()&&rt_strcmp(status,"paused")) { rt_mutex_release(&lock); return; }
    for(value=WATCH_IDLE;value<=WATCH_PAUSED;value++) if(!rt_strcmp(watch_name(value),status))break;
    if(value<=WATCH_PAUSED)state.status=value;else watch_pause(&state,now_ms());
    state.updated_ms=now_ms();
    if(update_count)product.event_count=count;
    render();rt_mutex_release(&lock);
}
int main(void) {
    watch_announce_init();
    watch_init(&state);
    watch_product_init(&product);
    rt_mutex_init(&lock,"watch",RT_IPC_FLAG_PRIO);
    lcd=rt_device_find("lcd");
    if (!lcd || rt_device_control(lcd,RTGRAPHIC_CTRL_GET_INFO,&info) != RT_EOK ||
        !info.framebuffer || info.pixel_format != RTGRAPHIC_PIXEL_FORMAT_RGB565 ||
        info.pitch < info.width*2) {
        lcd=RT_NULL;
        rt_kprintf("WATCH ERROR lcd unavailable\n");
    } else render();
    if(!rt_device_find("ST7102")) rt_hw_ST7102_port();
    touch=rt_device_find("ST7102");
    if(touch && rt_device_open(touch,RT_DEVICE_FLAG_RDONLY)!=RT_EOK) touch=RT_NULL;
    rt_kprintf("WATCH BOOT %s\n",WATCH_BUILD);
    usbh_initialize(0,USBHS_BASE,NULL);
    while (1) {
        rt_thread_mdelay(100);
        rt_mutex_take(&lock,RT_WAITING_FOREVER);
        poll_touch();
        if (!watch_standalone_running() && watch_expire(&state,now_ms())) {
            int result=render();
            rt_kprintf("WATCH TIMEOUT %u offline render=%d %08x\n",(unsigned)state.sequence,result,frame_hash);
        }
        if(lcd) {
            char voice[16],action[8];
            watch_voice_snapshot(voice,action);
            if(watch_face_key(watch_face_pose(state.status,voice,now_ms()))!=face_key)render();
        }
        rt_mutex_release(&lock);
    }
}
