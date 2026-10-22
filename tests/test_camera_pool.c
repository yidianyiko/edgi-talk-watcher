#include <assert.h>
#include <stdio.h>
#include "rtthread.h"
#include "chry_mempool.h"
struct fake_sem { unsigned count; } semaphore;
static unsigned waited;
rt_sem_t rt_sem_create(const char *name,unsigned initial,unsigned flags) {
 (void)name;(void)flags;semaphore.count=initial;return &semaphore;
}
int rt_sem_delete(rt_sem_t sem) { (void)sem;return 0; }
int rt_sem_take(rt_sem_t sem,int timeout) {
 if(sem->count){sem->count--;return 0;}
 assert(timeout>=0);waited+=(unsigned)timeout;return -RT_ETIMEOUT;
}
int rt_sem_release(rt_sem_t sem) {sem->count++;return 0;}
int main(void) {
 struct chry_mempool pool; uintptr_t blocks[2][2],*frame=NULL,*sent;
 assert(!chry_mempool_create(&pool,blocks,sizeof(blocks[0]),2));
 /* A new frame queue has no completed frames. It must wait, even though
    two free backing buffers are available to the producer. */
 assert(chry_mempool_recv(&pool,&frame,50)==-1);
 assert(waited==50);
 sent=chry_mempool_alloc(&pool);assert(sent!=NULL);
 assert(!chry_mempool_send(&pool,sent));
 assert(!chry_mempool_recv(&pool,&frame,50));assert(frame==sent);
 assert(waited==50);chry_mempool_free(&pool,frame);
 assert(chry_mempool_recv(&pool,&frame,50)==-1);assert(waited==100);
 rt_sem_delete(pool.out_sem);
 puts("camera pool: empty queue waits; only completed frames wake readers");
 return 0;
}
