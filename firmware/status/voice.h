#ifndef WATCH_VOICE_H
#define WATCH_VOICE_H
/* Voice state snapshot copies are guarded internally, and never hold the LCD lock. */
void watch_voice_snapshot(char status[16],char action[8]);
int watch_voice_begin(unsigned seconds);
void watch_voice_redraw(void);
#endif
