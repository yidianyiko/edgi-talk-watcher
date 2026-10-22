#include "status.h"
#include <assert.h>
#include <stdio.h>
int main(void) {
    struct watch_state s;
    watch_init(&s);
    assert(s.status == WATCH_OFFLINE);
    assert(watch_apply(&s, "1", "watching", 100) == 0);
    assert(s.status == WATCH_WATCHING && s.sequence == 1);
    assert(watch_expire(&s, 5099) == 0);
    assert(watch_expire(&s, 5100) == 1);
    assert(s.status == WATCH_OFFLINE);
    assert(watch_apply(&s, "2", "paused", 5200) == 0);
    assert(watch_apply(&s, "1", "event", 9000) == -2);
    assert(watch_apply(&s, "3", "nonsense", 9000) == -1);
    assert(watch_apply(&s, "4294967296", "event", 9000) == -1);
    assert(watch_apply(&s, "-1", "event", 9000) == -1);
    assert(s.status == WATCH_PAUSED && s.sequence == 2 && s.updated_ms == 5200);
    assert(watch_expire(&s, 10200) == 1);
    watch_init(&s);
    assert(watch_apply(&s, "1", "uncertain", UINT32_MAX - 1000) == 0);
    assert(watch_expire(&s, 3998) == 0);
    assert(watch_expire(&s, 3999) == 1);
    /* Local task/pause/next actions after long uptime need a fresh lease. */
    watch_init(&s);
    watch_pause(&s,100000);
    assert(s.status == WATCH_PAUSED && s.sequence == 0 && s.updated_ms == 100000);
    assert(watch_expire(&s,100001) == 0);
    assert(watch_expire(&s,104999) == 0);
    assert(watch_expire(&s,105000) == 1);
    assert(watch_apply(&s,"1","watching",110000) == 0);
    watch_pause(&s,120000);
    assert(s.sequence == 1 && s.status == WATCH_PAUSED && s.updated_ms == 120000);
    assert(watch_expire(&s,120001) == 0);
    puts("status: transitions and timeout passed");
}
