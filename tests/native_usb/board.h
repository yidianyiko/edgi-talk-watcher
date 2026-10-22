#ifndef WATCH_TEST_BOARD_H
#define WATCH_TEST_BOARD_H
#include <stdint.h>
extern uint32_t test_usb_registers[512];
#define USBHS_BASE ((uintptr_t)test_usb_registers)
#define usbhs_interrupt_usbhsctrl_IRQn 151
unsigned NVIC_GetEnableIRQ(int irq);
void NVIC_DisableIRQ(int irq);
void NVIC_EnableIRQ(int irq);
#define __DSB() ((void)0)
#define __ISB() ((void)0)
#endif
