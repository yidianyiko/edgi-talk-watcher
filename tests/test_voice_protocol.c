#include "voice_protocol.h"
#include <assert.h>
#include <stdio.h>
#include <string.h>
int main(void) {
 char h[512],action[8];
 assert(!watch_voice_header(h,sizeof(h),"192.168.7.1",8765,"abc_123","boot-1",192000));
 assert(strstr(h,"POST /api/board/voice HTTP/1.1\r\n"));
 assert(strstr(h,"X-Voice-Request: boot-1\r\n"));
 assert(strstr(h,"Content-Length: 192000\r\n"));
 assert(watch_voice_header(h,sizeof(h),"1.2.3.999",8765,"abc","id",32000));
 assert(watch_voice_header(h,sizeof(h),"1.2.3.4",8765,"bad\r\n","id",32000));
 assert(watch_voice_header(h,sizeof(h),"1.2.3.4",8765,"abc","bad id",32000));
 assert(watch_voice_header(h,sizeof(h),"1.2.3.4",8765,"abc","id",15999));
 assert(watch_voice_header(h,sizeof(h),"1.2.3.4",8765,"abc","id",256002));
 assert(watch_voice_header(h,8,"1.2.3.4",8765,"abc","id",32000));
 assert(!watch_voice_parse("HTTP/1.1 200 OK\r\nContent-Length: 9\r\n\r\nok pause\n",action));assert(!strcmp(action,"pause"));
 assert(!watch_voice_parse("HTTP/1.0 200 OK\r\n\r\nok start\n",action));assert(!strcmp(action,"start"));
 assert(!watch_voice_parse("HTTP/1.1 200 OK\r\n\r\nok task\n",action));assert(!strcmp(action,"task"));
 assert(watch_voice_parse("HTTP/1.1 503 Error\r\n\r\nok task\n",action));
 assert(watch_voice_parse("HTTP/1.1 200 OK\r\n\r\nok task\nextra",action));
 assert(watch_voice_parse("HTTP/1.1 200 OK\r\n\r\nok task",action));
 assert(watch_voice_http_code("HTTP/1.1 503 Unavailable\r\n")==503);
 assert(watch_voice_http_code("HTTP/1.0 200 OK\r\n")==200);
 assert(watch_voice_http_code("HTTP/1.1 50")==0);
 assert(watch_voice_http_code("secret 503")==0);
 puts("voice protocol: all checks passed");return 0;
}
