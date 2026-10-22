#ifndef CAMERA_NATIVE_RTTHREAD_H
#define CAMERA_NATIVE_RTTHREAD_H
#include <stdint.h>
typedef int rt_err_t;
typedef struct fake_sem *rt_sem_t;
#define RT_IPC_FLAG_FIFO 0
#define RT_EOK 0
#define RT_ETIMEOUT 2
#define RT_ERROR 1
#define RT_WAITING_FOREVER (-1)
rt_sem_t rt_sem_create(const char *, unsigned, unsigned);
int rt_sem_delete(rt_sem_t);
int rt_sem_take(rt_sem_t, int);
int rt_sem_release(rt_sem_t);
static inline int rt_tick_from_millisecond(uint32_t ms) { return (int)ms; }
#endif
