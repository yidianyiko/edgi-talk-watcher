// Hippo v1: fit-check prototype. Units mm. OpenSCAD 2021.01.
// XY = face, +Z = toward rear. Printed pieces are laid flat at Z=0.
part = "assembly";
$fn=64;
wall=2.8;
body_w=154;
body_h=142;
body_y=10;
depth=74;
camera_mount_z=64;
board_w=110;
board_h=69;
board_y=-12;
// Generous provisional window, NOT a verified glass or active-area dimension.
window_w=112;
window_h=70;
camera_y=65;
body_screws=[[-68,-43],[68,-43],[-68,55],[68,55]];
board_screws=[[-51,board_y-30.5],[51,board_y-30.5],[-51,board_y+30.5],[51,board_y+30.5]];
module rr(w,h,r){offset(r=r) square([w-2*r,h-2*r],center=true);}
module outline(){union(){translate([0,body_y])rr(body_w,body_h,28);translate([0,65])rr(124,52,8);for(s=[-1,1]){translate([s*59,80])circle(r=13);translate([s*33,73])circle(r=18);}}}
module window(extra=0){translate([0,board_y])rr(window_w+extra,window_h+extra,2);}
module fastener_points(){for(p=body_screws)translate(p)children();}
module camera_mount_points(){for(x=[-54,54],y=[-10,10])translate([x,camera_y+y])children();}
module front(){difference(){union(){linear_extrude(wall)difference(){outline();window();translate([0,camera_y])circle(r=15);}
 linear_extrude(depth-3)difference(){outline();offset(delta=-wall)outline();}
 fastener_points()linear_extrude(depth-3)circle(r=4.8);
 camera_mount_points()linear_extrude(camera_mount_z)circle(r=3.6);
 }
 // Shell screw pilot holes accessible from rear.
 translate([0,0,depth-15])fastener_points()linear_extrude(16)circle(d=2.8);
 translate([0,0,camera_mount_z-10])camera_mount_points()linear_extrude(11)circle(d=2.5);
 // Side service opening: generous provisional opening, not fitted USB cutouts.
 translate([-body_w/2-1,-38,16])cube([8,57,20]);
 // Right side acoustic openings.
 for(y=[-15,-7,1,9])translate([body_w/2-5,y,17])cube([9,2.5,17]);
 }}
module back(){difference(){linear_extrude(3)outline();
 fastener_points()translate([0,0,-1])linear_extrude(5)circle(d=3.4);
 for(p=board_screws)translate([p[0],p[1],-1])cylinder(d=3.4,h=5);
 for(x=[-35:7:35])translate([x,37,-1])linear_extrude(5)rr(3,19,1.4);
 translate([0,-50,-1])linear_extrude(5)rr(20,9,2);
 // Camera carriage adjustment holes, accepts screws/nylon spacers.
 }}
module lip(){linear_extrude(4)difference(){translate([0,board_y])rr(132,90,15);window();}}
module muzzle(){difference(){linear_extrude(7)translate([0,40])rr(108,25,12);
 for(x=[-29,29])translate([x,42,-1])linear_extrude(9)scale([1.6,1])circle(r=3.3);
 // Recess overlapping lip and upper teeth so separate prints seat together.
 translate([0,0,3])lip();
 for(x=[-50,50])translate([x,board_y+40,-0.1])linear_extrude(3.2)rr(8.4,10.4,2.5);
 }}
module nostril(){linear_extrude(1.5)scale([1.6,1])circle(r=3.8);}
module tooth(){linear_extrude(3)rr(8,10,2.5);}
module eye(){linear_extrude(3)circle(r=10);}
module pupil(){linear_extrude(1.5)circle(r=4);}
module ear_inner(){linear_extrude(2)scale([0.7,1])circle(r=8);}
module spacer(){difference(){cylinder(d=8,h=depth-28);translate([0,0,-1])cylinder(d=2.8,h=depth-26);}}
// Whole 95 mm webcam retained with ties; clip remains installed.
module camera_tray(){difference(){union(){
 linear_extrude(2)rr(118,42,3);
 // 34.8 mm supports with 0.2 mm pad allowance register the camera body rear against the tray.
 for(x=[-38,38])translate([x-6,-10,2])cube([12,20,34.8]);
 // Stiffening rails; open sides accommodate cable and ties.
 for(y=[-19])translate([-49,y-1.2,2])cube([98,2.4,3]);
 }
 for(x=[-54,54],y=[-10,10])translate([x,y,-1])linear_extrude(7)hull(){translate([0,-2])circle(d=3.4);translate([0,2])circle(d=3.4);}
 for(x=[-45,45],y=[-13,13])translate([x,y,-1])linear_extrude(7)rr(4,9,1);
 // Rear cable passage, plus open rail ends for alternate routing.
 translate([0,0,-1])linear_extrude(7)rr(30,14,3);
 }}
// Conservative clearance volumes, not an exact camera model.
module camera_envelope(){
 translate([-48.5,camera_y-17,5])cube([97,34,24]);
 translate([-22,camera_y-38.5,5])cube([44,23.5,58]);
}
module foot(){difference(){union(){linear_extrude(8)rr(38,depth+28,12);
 // Slide-on socket for 50 mm-deep body bottom; requires fit check.
 translate([0,0,8])linear_extrude(3)difference(){rr(34,depth+7,5);square([40,depth+0.8],center=true);}}
 }}
module fit_frame(){linear_extrude(1.2)difference(){translate([0,board_y])rr(122,80,3);window();}}
module board_template(){linear_extrude(1.2)difference(){union(){translate([0,board_y])square([110,69],center=true);}translate([0,board_y])square([94,53],center=true);for(p=board_screws)translate(p)circle(d=4.2);}}
module assembly(){color("#b69ac8")front();color("#9c80af")translate([0,0,depth-3])back();
 color("#e8acbd")translate([0,0,-4])lip();color("#c9afd9")translate([0,0,-7])muzzle();
 for(x=[-29,29])color("#685374")translate([x,42,-8.5])nostril();
 for(s=[-1,1]){
 color("ivory")for(y=[board_y-40,board_y+40])translate([s*50,y,-7])tooth();
 color("ivory")translate([s*33,73,-3])eye();color("#302e3c")translate([s*33,73,-4.5])pupil();
 color("#dfb2c6")translate([s*59,80,-2])ear_inner();
 color("#aa8cba")translate([s*30,-69,depth/2])rotate([-90,0,0])foot();
 }
 color("orange")translate([0,camera_y,camera_mount_z+2])rotate([180,0,0])camera_tray();
 color([0.2,0.2,0.2,0.35])camera_envelope();
 // Transparent, provisional screen envelope shown for scale only.
 color([0.08,0.13,0.17,0.85])translate([-55,board_y-34.5,3])cube([110,69,3]);
 color("#202937")translate([0,camera_y,-0.5])cylinder(d=14,h=2);
}
if(part=="front")front();else if(part=="back")back();else if(part=="lip")lip();else if(part=="muzzle")muzzle();else if(part=="nostril")nostril();else if(part=="tooth")tooth();else if(part=="eye")eye();else if(part=="pupil")pupil();else if(part=="ear_inner")ear_inner();else if(part=="spacer")spacer();else if(part=="camera_tray")camera_tray();else if(part=="foot")foot();else if(part=="fit_frame")fit_frame();else if(part=="board_template")board_template();else if(part=="assembly")assembly();
