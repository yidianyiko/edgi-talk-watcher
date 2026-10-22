#ifndef WATCH_PRODUCT_H
#define WATCH_PRODUCT_H
#include <stdint.h>
struct watch_product { uint32_t task_id, event_count, request_id; char task_label[33], action[8]; };
void watch_product_init(struct watch_product *p);
int watch_product_task(struct watch_product *p,const char *id,const char *label);
int watch_product_count(struct watch_product *p,const char *count);
int watch_product_action(struct watch_product *p,const char *action);
#endif
