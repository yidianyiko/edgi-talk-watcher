#ifndef WATCH_FACE_H
#define WATCH_FACE_H
#include <stdint.h>
#include "status.h"
enum watch_expression { FACE_OFFLINE, FACE_IDLE, FACE_WATCHING, FACE_ALERT,
 FACE_UNCERTAIN, FACE_SLEEPY, FACE_LISTENING, FACE_THINKING };
struct watch_face { enum watch_expression expression; int gaze,closed; };
typedef void (*watch_face_rect)(int,int,int,int,unsigned short,void*);
struct watch_face watch_face_pose(enum watch_status status,const char *voice,uint32_t now);
unsigned watch_face_key(struct watch_face face);
void watch_face_draw(int width,int height,struct watch_face face,watch_face_rect draw,void *context);
#endif
