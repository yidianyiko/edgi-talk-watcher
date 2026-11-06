"""Check selected assembled solid pairs with CGAL intersections."""
from pathlib import Path
import subprocess,json,struct
import trimesh
ROOT=Path(__file__).resolve().parent
pairs={
 'camera_envelope_shell':'front();camera_envelope();',
 'camera_envelope_back':'translate([0,0,depth-3])back();camera_envelope();',
 'camera_envelope_tray':'translate([0,camera_y,camera_mount_z+2])rotate([180,0,0])camera_tray();camera_envelope();',
 'lip_muzzle':'translate([0,0,-4])lip(); translate([0,0,-7])muzzle();',
 'upper_teeth_muzzle':'union(){for(x=[-50,50])translate([x,board_y+40,-7])tooth();}translate([0,0,-7])muzzle();',
 'camera_tray_shell':'front();translate([0,camera_y,camera_mount_z+2])rotate([180,0,0])camera_tray();',
 'feet_shell':'front();union(){for(s=[-1,1])translate([s*30,-69,depth/2])rotate([-90,0,0])foot();}',
 'feet_lip':'translate([0,0,-4])lip();union(){for(s=[-1,1])translate([s*30,-69,depth/2])rotate([-90,0,0])foot();}',
 'front_back':'front();translate([0,0,depth-3])back();',
}
rows=[]
for name,code in pairs.items():
 source=ROOT/f'.clearance-{name}.scad';target=ROOT/f'.clearance-{name}.stl'
 source.write_text('include <hippo.scad>\nintersection(){'+code+'}\n')
 p=subprocess.run(['openscad','--hardwarnings','--export-format','binstl','-D','part="none"','-o',str(target),str(source)],capture_output=True,text=True)
 empty='Current top level object is empty.' in p.stderr and not target.exists()
 volume=0.0
 if target.exists():
  triangles=struct.unpack('<I',target.read_bytes()[80:84])[0]
  if triangles:
   mesh=trimesh.load_mesh(target);volume=abs(float(mesh.volume))
  empty=volume<0.00001 and 'ERROR:' not in p.stderr
 (ROOT/f'{name}.clearance.log').write_text(p.stdout+p.stderr)
 source.unlink()
 row={'pair':name,'no_volumetric_overlap':empty,'intersection_volume_mm3':volume};rows.append(row)
 print(name,'PASS' if empty else 'FAIL',flush=True)
 if target.exists():target.unlink()
 assert empty,p.stderr
(ROOT/'clearance-report.json').write_text(json.dumps({'scope':'selected nominal assembled part intersections; no physical hardware acceptance','pairs':rows},indent=2))
