#ifndef TEST_RTTHREAD_H
#define TEST_RTTHREAD_H
#include <stddef.h>
#include <stdint.h>
typedef int rt_base_t;
typedef int rt_int32_t;
typedef long rt_ssize_t;
rt_base_t rt_hw_interrupt_disable(void);
void rt_hw_interrupt_enable(rt_base_t value);
uint32_t rt_tick_get_millisecond(void);
void rt_thread_mdelay(unsigned milliseconds);
#endif
