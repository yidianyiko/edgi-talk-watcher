#ifndef WATCH_GATEWAY_H
#define WATCH_GATEWAY_H
#include <stdint.h>
#include <stddef.h>
struct watch_reply { char status[10]; uint32_t event_count; };
int watch_gateway_header(char *out,size_t capacity,const char *host,unsigned port,const char *token,uint32_t task_id,const char *session,uint32_t frame_ms,int reset);
int watch_gateway_parse(const char *http,struct watch_reply *reply);
int watch_gateway_budget(uint32_t now,uint32_t start,unsigned seconds,unsigned calls,unsigned maxcalls,int cancelled);
#endif
