#include "voice_protocol.h"
#include <stdio.h>
#include <string.h>
static int safe(const char *p) {
 const char *start=p;
 if(!p||!*p||strlen(p)>64)return 0;
 for(;*p;p++)if(!((*p>='a'&&*p<='z')||(*p>='A'&&*p<='Z')||(*p>='0'&&*p<='9')||*p=='_'||*p=='-'||*p=='.'))return 0;
 return p!=start;
}
int watch_voice_header(char *out,size_t capacity,const char *host,unsigned port,const char *token,const char *request,size_t bytes) {
 unsigned i;const char *p=host;int n;
 if(!out||!p||!port||port>65535||!safe(token)||!safe(request)||bytes<16000||bytes>256000||bytes%2)return -1;
 for(i=0;i<4;i++){unsigned value=0,digits=0;while(*p>='0'&&*p<='9'){value=value*10+(unsigned)(*p++-'0');if(++digits>3||value>255)return -1;}if(!digits)return -1;if(i<3){if(*p++!='.')return -1;}else if(*p)return -1;}
 n=snprintf(out,capacity,"POST /api/board/voice HTTP/1.1\r\nHost: %s:%u\r\nAuthorization: Bearer %s\r\nX-Voice-Request: %s\r\nContent-Type: application/octet-stream\r\nContent-Length: %u\r\nConnection: close\r\n\r\n",host,port,token,request,(unsigned)bytes);
 return n<0||(size_t)n>=capacity?-1:0;
}
int watch_voice_parse(const char *http,char action[8]) {
 const char *body;
 if(!http||!action||(strncmp(http,"HTTP/1.1 200 ",13)&&strncmp(http,"HTTP/1.0 200 ",13)))return -1;
 body=strstr(http,"\r\n\r\n");if(!body)return -1;body+=4;
 if(!strcmp(body,"ok pause\n"))strcpy(action,"pause");
 else if(!strcmp(body,"ok start\n"))strcpy(action,"start");
 else if(!strcmp(body,"ok task\n"))strcpy(action,"task");else return -1;
 return 0;
}

/* Safe diagnostics: expose only the numeric HTTP code, never server content. */
int watch_voice_http_code(const char *http) {
 unsigned i;int code=0;
 if(!http||strlen(http)<13||(strncmp(http,"HTTP/1.1 ",9)&&strncmp(http,"HTTP/1.0 ",9)))return 0;
 for(i=9;i<12;i++){if(http[i]<'0'||http[i]>'9')return 0;code=code*10+http[i]-'0';}
 return http[12]==' '?code:0;
}
