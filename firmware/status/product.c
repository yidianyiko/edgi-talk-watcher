#include "product.h"
#include <string.h>
static int number(const char *s,uint32_t *out) {
 uint32_t n=0; if(!s||!*s) return -1;
 for(;*s;s++) { unsigned d=(unsigned)(*s-'0'); if(d>9||n>(UINT32_MAX-d)/10) return -1; n=n*10+d; }
 *out=n; return 0;
}
void watch_product_init(struct watch_product *p) { memset(p,0,sizeof(*p)); strcpy(p->task_label,"NO TASK"); strcpy(p->action,"none"); }
int watch_product_task(struct watch_product *p,const char *id,const char *label) {
 uint32_t n; const char *s;
 if(number(id,&n)||!n||!label||!*label||strlen(label)>32) return -1;
 for(s=label;*s;s++) if(!((*s>='A'&&*s<='Z')||(*s>='a'&&*s<='z')||(*s>='0'&&*s<='9')||*s=='_')) return -1;
 p->task_id=n; strcpy(p->task_label,label); return 0;
}
int watch_product_count(struct watch_product *p,const char *count) { uint32_t n; if(number(count,&n)) return -1; p->event_count=n; return 0; }
int watch_product_action(struct watch_product *p,const char *action) {
 if(!action||(strcmp(action,"start")&&strcmp(action,"pause")&&strcmp(action,"next")&&strcmp(action,"history"))||p->request_id==UINT32_MAX) return -1;
 p->request_id++; strcpy(p->action,action); return 0;
}
