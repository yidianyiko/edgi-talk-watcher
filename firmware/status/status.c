#include "status.h"
#include <string.h>
#include <stdint.h>
static const char *names[] = {"offline", "idle", "watching", "event", "uncertain", "paused"};
void watch_init(struct watch_state *s) { memset(s, 0, sizeof(*s)); }
void watch_pause(struct watch_state *s,uint32_t now) { s->status=WATCH_PAUSED; s->updated_ms=now; }
const char *watch_name(enum watch_status status) {
    return status >= WATCH_OFFLINE && status <= WATCH_PAUSED ? names[status] : "invalid";
}
int watch_apply(struct watch_state *s, const char *sequence, const char *status, uint32_t now) {
    uint32_t n = 0;
    const char *p = sequence;
    enum watch_status value;
    if (!p || !*p || !status) return -1;
    while (*p) {
        if (*p < '0' || *p > '9' || n > (UINT32_MAX - (unsigned)(*p - '0')) / 10) return -1;
        n = n * 10 + (unsigned)(*p++ - '0');
    }
    if (n <= s->sequence) return -2;
    for (value = WATCH_IDLE; value <= WATCH_PAUSED; value++)
        if (!strcmp(status, names[value])) break;
    if (value > WATCH_PAUSED) return -1;
    s->status = value; s->sequence = n; s->updated_ms = now;
    return 0;
}
int watch_expire(struct watch_state *s, uint32_t now) {
    if (s->status != WATCH_OFFLINE && (uint32_t)(now - s->updated_ms) >= 5000) {
        s->status = WATCH_OFFLINE;
        return 1;
    }
    return 0;
}
