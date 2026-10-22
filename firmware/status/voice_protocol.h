#ifndef WATCH_VOICE_PROTOCOL_H
#define WATCH_VOICE_PROTOCOL_H
#include <stddef.h>
int watch_voice_header(char *out,size_t capacity,const char *host,unsigned port,const char *token,const char *request,size_t bytes);
int watch_voice_http_code(const char *http);
int watch_voice_parse(const char *http,char action[8]);
#endif
