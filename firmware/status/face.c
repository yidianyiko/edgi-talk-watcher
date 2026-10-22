#include "face.h"
#include <string.h>
struct watch_face watch_face_pose(enum watch_status status,const char *voice,uint32_t now) {
 struct watch_face f={FACE_OFFLINE,0,0};
 static const enum watch_expression expressions[]={FACE_OFFLINE,FACE_IDLE,FACE_WATCHING,FACE_ALERT,FACE_UNCERTAIN,FACE_SLEEPY};
 if((unsigned)status<sizeof(expressions)/sizeof(expressions[0]))f.expression=expressions[status];
 if(voice&&!strcmp(voice,"LISTENING"))f.expression=FACE_LISTENING;
 else if(voice&&!strcmp(voice,"RECOGNIZING"))f.expression=FACE_THINKING;
 if(f.expression==FACE_WATCHING) {static const int gaze[]={0,10,0,-10};f.gaze=gaze[(now/1800)%4];}
 if(f.expression==FACE_THINKING)f.gaze=((now/600)%2)?8:-8;
 f.closed=now%4800>=4620&&f.expression!=FACE_LISTENING;
 return f;
}
unsigned watch_face_key(struct watch_face f){return (unsigned)f.expression*128u+(unsigned)(f.gaze+16)*2u+(unsigned)f.closed;}
struct canvas {int width,height;watch_face_rect draw;void *context;};
static void box(struct canvas *c,int x,int y,int w,int h,unsigned short color){
 if(x<0){w+=x;x=0;}if(y<0){h+=y;y=0;}
 if(x+w>c->width)w=c->width-x;
 if(y+h>c->height)h=c->height-y;
 if(w>0&&h>0)c->draw(x,y,w,h,color,c->context);
}
static void rounded(struct canvas *c,int x,int y,int w,int h,int radius,unsigned short color){
 int row,dx;
 if(radius>w/2)radius=w/2;
 if(radius>h/2)radius=h/2;
 for(row=0;row<h;row++){
  int dy=row<radius?radius-row-1:row>=h-radius?row-(h-radius):0;
  dx=0;
  while(dx<radius&&(radius-dx-1)*(radius-dx-1)+dy*dy>radius*radius)dx++;
  box(c,x+dx,y+row,w-2*dx,1,color);
 }
}
void watch_face_draw(int width,int height,struct watch_face f,watch_face_rect draw,void *context){
 struct canvas c={width,height,draw,context};int side;
 int ew=112*width/480,eh=132*height/800,cy=296*height/800;
 unsigned short color=0x05ff;
 if(!draw||width<48||height<80)return;
 switch(f.expression){
 case FACE_OFFLINE:eh=20*height/800;color=0x630c;break;
 case FACE_SLEEPY:eh=28*height/800;color=0x0392;break;
 case FACE_IDLE:eh=100*height/800;break;
 case FACE_ALERT:ew=136*width/480;eh=150*height/800;color=0xfd20;break;
 case FACE_UNCERTAIN:eh=96*height/800;color=0xfec0;break;
 case FACE_LISTENING:eh=156*height/800;color=0x6fff;break;
 case FACE_THINKING:eh=84*height/800;color=0xa51f;break;
 default:break;
 }
 if(f.closed)eh=10*height/800;
 for(side=0;side<2;side++){
  int cx=width*(side?68:32)/100;
  int h=eh-(f.expression==FACE_UNCERTAIN&&side&&!f.closed?20*height/800:0);
  rounded(&c,cx-ew/2,cy-h/2,ew,h,ew/3,color);
  if(h>=48*height/800&&!f.closed){
   int pw=44*width/480,ph=h*58/100,px=cx+f.gaze*width/480;
   rounded(&c,px-pw/2,cy-ph/2,pw,ph,pw/2,0x0841);
   rounded(&c,px+4*width/480,cy-ph/2+9*height/800,10*width/480,14*height/800,3,0xffff);
  }
 }
}
