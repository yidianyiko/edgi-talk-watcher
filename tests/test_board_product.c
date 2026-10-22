#include "product.h"
#include <assert.h>
#include <stdio.h>
#include <string.h>
int main(void) {
 struct watch_product p; watch_product_init(&p);
 assert(!strcmp(p.task_label,"NO TASK"));
 assert(watch_product_task(&p,"12","PERSON_APPEARS")==0);
 assert(p.task_id==12 && !strcmp(p.task_label,"PERSON_APPEARS"));
 assert(watch_product_task(&p,"13","bad;command")==-1 && p.task_id==12);
 assert(watch_product_count(&p,"4294967295")==0 && p.event_count==4294967295u);
 assert(watch_product_count(&p,"4294967296")==-1);
 assert(watch_product_action(&p,"start")==0 && p.request_id==1);
 assert(watch_product_action(&p,"erase")==-1 && p.request_id==1);
 assert(watch_product_action(&p,"pause")==0 && !strcmp(p.action,"pause"));
 assert(watch_product_action(&p,"next")==0);
 assert(watch_product_action(&p,"history")==0 && p.request_id==4);
 assert(watch_product_task(&p,"0","X")==-1);
 assert(watch_product_task(&p,"2","ABCDEFGHIJKLMNOPQRSTUVWXYZ1234567")==-1);
 p.request_id=UINT32_MAX;
 assert(watch_product_action(&p,"start")==-1 && p.request_id==UINT32_MAX);
 assert(watch_product_count(&p,"-1")==-1);
 assert(watch_product_task(&p,"4294967296","A")==-1);
 puts("board product: task validation, counter overflow and control requests passed");
}
