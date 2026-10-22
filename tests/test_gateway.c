#include "gateway.h"
#include <assert.h>
#include <stdio.h>
#include <string.h>
int main(void) {
 char out[640]; struct watch_reply r;
 assert(watch_gateway_header(out,sizeof out,"192.168.1.5",5000,"abc_123",12,"test_session",1000,1)==0);
 assert(strstr(out,"POST /api/board/observe HTTP/1.1\r\n"));
 assert(strstr(out,"X-Watch-Session: test_session\r\n"));
 assert(strstr(out,"X-Watch-Time: 1000\r\n"));
 assert(strstr(out,"X-Watch-Reset: 1\r\n"));
 assert(strstr(out,"Content-Length: 153600\r\n"));
 assert(strstr(out,"Authorization: Bearer abc_123\r\n"));
 assert(watch_gateway_header(out,sizeof out,"1\r\nX: x",5000,"abc",12,"test_session",1000,1)==-1);
 assert(watch_gateway_header(out,sizeof out,"192.168.1.5",5000,"bad\r\n",12,"test_session",1000,1)==-1);
 assert(watch_gateway_parse("HTTP/1.1 200 OK\r\nContent-Length: 9\r\n\r\nevent 17\n",&r)==0);
 assert(!strcmp(r.status,"event")&&r.event_count==17);
 assert(watch_gateway_parse("HTTP/1.1 500 Error\r\n\r\nevent 17\n",&r)==-1);
 assert(watch_gateway_parse("HTTP/1.1 200 OK\r\n\r\nevent 4294967296\n",&r)==-1);
 assert(watch_gateway_parse("HTTP/1.1 200 OK\r\n\r\nevent 17evil\n",&r)==-1);
 assert(watch_gateway_parse("HTTP/1.1 200 OK\r\n\r\nwatching 17\n",&r)==0);
 assert(watch_gateway_parse("HTTP/1.1 200 OK\r\n\r\nuncertain 17\n",&r)==0);
 assert(watch_gateway_parse("HTTP/1.1 200 OK\r\n\r\npaused 17\n",&r)==0);
 assert(watch_gateway_budget(4999,0,5,0,1,0)==1);
 assert(watch_gateway_budget(5000,0,5,0,1,0)==0);
 assert(watch_gateway_budget(10,0,5,1,1,0)==0);
 assert(watch_gateway_budget(10,0,5,0,1,1)==0);
 assert(watch_gateway_budget(3998,UINT32_MAX-1000,5,0,1,0)==1);
 assert(watch_gateway_budget(3999,UINT32_MAX-1000,5,0,1,0)==0);
 puts("gateway: HTTP request validation and response rejection passed");
}
