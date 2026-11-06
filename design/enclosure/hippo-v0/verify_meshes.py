"""Offline geometry checks; these do not certify physical hardware fit."""
from pathlib import Path
import json
import numpy as np
import trimesh
from export import PARTS
ROOT=Path(__file__).resolve().parent

def components(faces,n):
 parent=list(range(n))
 def root(a):
  while parent[a]!=a:
   parent[a]=parent[parent[a]];a=parent[a]
  return a
 for a,b,c in faces:
  a,b,c=int(a),int(b),int(c)
  parent[root(b)]=root(a);parent[root(c)]=root(a)
 return len({root(int(i)) for i in np.unique(faces)})
rows=[]
for p in PARTS:
 m=trimesh.load_mesh(ROOT/f'{p}.stl')
 dims=m.extents
 row={'part':p,'mm':dims.round(3).tolist(),'watertight':bool(m.is_watertight),'consistent_winding':bool(m.is_winding_consistent),'positive_volume':bool(m.volume>0),'connected_components':components(m.faces,len(m.vertices)),'fits_220x220x250':bool(dims[0]<=220 and dims[1]<=220 and dims[2]<=250),'minimum_z':round(float(m.bounds[0,2]),4),'volume_cm3':round(float(m.volume)/1000,2)}
 assert row['watertight'] and row['consistent_winding'] and row['positive_volume'],row
 assert row['connected_components']==1,row
 assert row['fits_220x220x250'] and abs(row['minimum_z'])<0.001,row
 rows.append(row)
 print(p,'PASS',row['mm'])
(ROOT/'mesh-report.json').write_text(json.dumps({'status':'PASS','scope':'mesh integrity and nominal printer envelope only; not slicing or physical fit acceptance','trimesh':trimesh.__version__,'parts':rows},indent=2))
print(f'{len(rows)} / {len(PARTS)} mesh checks PASS')
