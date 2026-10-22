#include "gateway.h"
#include <string.h>
#include <stdio.h>
static int ipv4(const char *p) {
 int i;
 if(!p)return 0;
 for(i=0;i<4;i++) {
  unsigned n=0,d=0;
  while(*p>='0'&&*p<='9') { n=n*10+(unsigned)(*p++-'0');if(++d>3||n>255)return 0; }
  if(!d)return 0;
  if(i<3){if(*p++!='.')return 0;}else if(*p)return 0;
 }
 return 1;
}
int watch_gateway_header(char *out,size_t capacity,const char *host,unsigned port,const char *token,uint32_t task_id,const char *session,uint32_t frame_ms,int reset) {
 const char *p;int n;
 if(!out||!ipv4(host)||!port||port>65535||!task_id||!token||!*token||strlen(token)>64)return -1;
 for(p=token;*p;p++)if(!((*p>='a'&&*p<='z')||(*p>='A'&&*p<='Z')||(*p>='0'&&*p<='9')||*p=='_'||*p=='-'||*p=='.'))return -1;
 if(!session||!*session||strlen(session)>64)return -1;
 for(p=session;*p;p++)if(!((*p>='a'&&*p<='z')||(*p>='A'&&*p<='Z')||(*p>='0'&&*p<='9')||*p=='_'||*p=='-'))return -1;
 n=snprintf(out,capacity,"POST /api/board/observe HTTP/1.1\r\nHost: %s:%u\r\nAuthorization: Bearer %s\r\nX-Watch-Task: %u\r\nX-Watch-Session: %s\r\nX-Watch-Time: %u\r\nX-Watch-Reset: %u\r\nX-Watch-Width: 320\r\nX-Watch-Height: 240\r\nContent-Type: application/octet-stream\r\nContent-Length: 153600\r\nConnection: close\r\n\r\n",host,port,token,(unsigned)task_id,session,(unsigned)frame_ms,(unsigned)(reset!=0));
 return n<0||(size_t)n>=capacity?-1:0;
}
int watch_gateway_parse(const char *http,struct watch_reply *reply) {
 const char *body,*p,*status;uint32_t n=0;size_t length;
 if(!http||!reply||(strncmp(http,"HTTP/1.1 200 ",13)&&strncmp(http,"HTTP/1.0 200 ",13)))return -1;
 body=strstr(http,"\r\n\r\n");if(!body)return -1;body+=4;
 p=strchr(body,' ');if(!p)return -1;length=(size_t)(p-body);
 if(length==5&&!strncmp(body,"event",5))status="event";
 else if(length==8&&!strncmp(body,"watching",8))status="watching";
 else if(length==9&&!strncmp(body,"uncertain",9))status="uncertain";
 else if(length==6&&!strncmp(body,"paused",6))status="paused";else return -1;
 p++;if(*p<'0'||*p>'9')return -1;
 for(;*p>='0'&&*p<='9';p++){unsigned d=(unsigned)(*p-'0');if(n>(UINT32_MAX-d)/10)return -1;n=n*10+d;}
 if(*p=='\r')p++;
 if(*p++!='\n'||*p)return -1;
 strcpy(reply->status,status);reply->event_count=n;return 0;
}
int watch_gateway_budget(uint32_t now,uint32_t start,unsigned seconds,unsigned calls,unsigned maxcalls,int cancelled) {
 return !cancelled&&seconds>0&&seconds<=86400&&maxcalls>0&&calls<maxcalls&&(uint32_t)(now-start)<seconds*1000u;
}
