#ifndef WATCH_STATUS_H
#define WATCH_STATUS_H
#include <stdint.h>
enum watch_status { WATCH_OFFLINE, WATCH_IDLE, WATCH_WATCHING, WATCH_EVENT,
                    WATCH_UNCERTAIN, WATCH_PAUSED };
struct watch_state { enum watch_status status; uint32_t sequence, updated_ms; };
void watch_init(struct watch_state *s);
void watch_pause(struct watch_state *s,uint32_t now);
int watch_apply(struct watch_state *s, const char *sequence, const char *status, uint32_t now);
int watch_expire(struct watch_state *s, uint32_t now);
const char *watch_name(enum watch_status status);
#endif
