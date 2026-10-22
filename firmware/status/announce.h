#ifndef WATCH_ANNOUNCE_H
#define WATCH_ANNOUNCE_H
int watch_audio_claim(unsigned owner);
void watch_audio_release(unsigned owner);
int watch_announce_init(void);
#endif
