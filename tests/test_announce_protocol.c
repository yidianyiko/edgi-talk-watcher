#include "announce_protocol.h"
#include <assert.h>
#include <stdio.h>
#include <string.h>
int main(void) {
 struct watch_announce_policy p={0};
 assert(watch_announce_request(&p,"abc")<0);
 assert(watch_announce_request(&p,"0123456789abcdef0123456789abcdef")==0);
 assert(watch_announce_request(&p,"0123456789abcdef0123456789abcdef")==1);
 assert(watch_announce_request(&p,"1123456789abcdef0123456789abcdef")==-2);
 watch_announce_finish(&p);
 assert(watch_announce_request(&p,"0123456789abcdef0123456789abcdef")==1);
 assert(watch_announce_request(&p,"1123456789abcdef0123456789abcdef")==0);
 assert(watch_mulaw_decode(255)==0);assert(watch_mulaw_decode(127)==0);
 assert(watch_mulaw_decode(0)==-32124);assert(watch_mulaw_decode(128)==32124);
 puts("PASS announcement identity, duplicate/busy policy and G.711 reference vectors");return 0;
}
