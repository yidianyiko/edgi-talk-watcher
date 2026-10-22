#include "announce_protocol.h"
#include <string.h>
int watch_announce_request(struct watch_announce_policy *p,const char *id) {
 unsigned i;if(!id||strlen(id)!=32)return -1;
 for(i=0;i<32;i++)if(!((id[i]>='0'&&id[i]<='9')||(id[i]>='a'&&id[i]<='f')))return -1;
 if(!strcmp(id,p->last))return 1;
 if(p->busy)return -2;
 strcpy(p->last,id);p->busy=1;return 0;
}
void watch_announce_finish(struct watch_announce_policy *p){p->busy=0;}
int16_t watch_mulaw_decode(uint8_t value) {
 unsigned u=(unsigned)(uint8_t)~value;int t=((int)(u&15)<<3)+132;
 t<<=(u>>4)&7;return (int16_t)((u&128)?132-t:t-132);
}
