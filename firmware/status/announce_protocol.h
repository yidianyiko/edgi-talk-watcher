#ifndef WATCH_ANNOUNCE_PROTOCOL_H
#define WATCH_ANNOUNCE_PROTOCOL_H
#include <stdint.h>
struct watch_announce_policy {char last[33];int busy;};
/* 0 queued, 1 same event already accepted, -2 busy (retry), -1 invalid. */
int watch_announce_request(struct watch_announce_policy *p,const char *id);
void watch_announce_finish(struct watch_announce_policy *p);
int16_t watch_mulaw_decode(uint8_t value);
#endif
