#include <assert.h>
#include <stdio.h>
#include <string.h>
#include <stdlib.h>
#include "face.h"
static unsigned short pixels[480*800];
static unsigned calls;
static void rect(int x,int y,int w,int h,unsigned short color,void *ctx) {
 int i,j;(void)ctx;
 assert(x>=0&&y>=0&&w>0&&h>0&&x+w<=480&&y+h<=800);
 for(j=y;j<y+h;j++)for(i=x;i<x+w;i++)pixels[j*480+i]=color;
 calls++;
}
int main(int argc,char **argv) {
 struct watch_face f=watch_face_pose(WATCH_WATCHING,"READY",1000);
 assert(f.expression==FACE_WATCHING);
 assert(watch_face_pose(WATCH_PAUSED,"READY",1000).expression==FACE_SLEEPY);
 assert(watch_face_pose(WATCH_EVENT,"DONE",1000).expression==FACE_ALERT);
 assert(watch_face_pose(WATCH_PAUSED,"LISTENING",1000).expression==FACE_LISTENING);
 assert(watch_face_pose(WATCH_WATCHING,"RECOGNIZING",1000).expression==FACE_THINKING);
 assert(watch_face_pose(WATCH_WATCHING,"READY",4700).closed);
 assert(!watch_face_pose(WATCH_WATCHING,"READY",4800).closed);
 assert(watch_face_key(watch_face_pose(WATCH_WATCHING,"READY",1000))!=watch_face_key(watch_face_pose(WATCH_WATCHING,"READY",2000)));
 for(int mode=FACE_OFFLINE;mode<=FACE_THINKING;mode++){
  for(int closed=0;closed<=1;closed++){
   struct watch_face pose={(enum watch_expression)mode,-10,closed};
   watch_face_draw(480,800,pose,rect,0);
  }
 }
 memset(pixels,0,sizeof(pixels));
 if(argc>2)f.expression=(enum watch_expression)atoi(argv[2]);
 watch_face_draw(480,800,f,rect,0);
 assert(calls>10);
 assert(pixels[296*480+110]!=0); /* left iris */
 assert(pixels[296*480+370]!=0); /* right iris */
 assert(pixels[296*480+240]==0); /* clear gap */
 assert(pixels[100*480+100]==0&&pixels[550*480+100]==0); /* labels untouched */
 if(argc>1){FILE *out=fopen(argv[1],"wb");int i;assert(out);fprintf(out,"P6\n480 800\n255\n");
  for(i=0;i<480*800;i++){unsigned short p=pixels[i];fputc(((p>>11)&31)*255/31,out);fputc(((p>>5)&63)*255/63,out);fputc((p&31)*255/31,out);}fclose(out);}
 puts("face states, blink and screen bounds OK");return 0;
}
