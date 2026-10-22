#ifndef WATCH_STANDALONE_H
#define WATCH_STANDALONE_H
#include <stdint.h>
int watch_standalone_running(void);
void watch_standalone_stop(void);
int watch_standalone_cancelled(void);
uint32_t watch_local_task_id(void);
void watch_local_result(const char *status,uint32_t count,int update_count);
#endif
