#ifndef WATCH_TEST_RTTHREAD_H
#define WATCH_TEST_RTTHREAD_H
#include <pthread.h>
#include <stdint.h>
struct rt_mutex { pthread_mutex_t native; };
typedef uintptr_t rt_thread_t;
#define RT_WAITING_FOREVER -1
#define RT_IPC_FLAG_PRIO 1
#define INIT_APP_EXPORT(fn) int test_camera_stop_init(void) { return fn(); }
void rt_thread_mdelay(unsigned milliseconds);
int rt_mutex_init(struct rt_mutex *, const char *, unsigned);
int rt_mutex_take(struct rt_mutex *, int);
int rt_mutex_release(struct rt_mutex *);
rt_thread_t rt_thread_self(void);
#endif
