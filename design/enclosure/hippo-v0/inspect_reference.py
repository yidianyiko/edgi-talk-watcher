import mmap,re,json,array
from pathlib import Path
out={}
for name,root in [('basic',90521),('core',70367)]:
 with open('/tmp/rt-enclosure-reference/'+name+'.stp','rb') as f:
  mm=mmap.mmap(f.fileno(),0,access=mmap.ACCESS_READ)
  offsets=array.array('Q',[0])*11000000
  for m in re.finditer(rb'(?m)^#(\d+)=',mm):
   i=int(m[1])
   if i>=len(offsets):offsets.extend(array.array('Q',[0])*(i-len(offsets)+1000000))
   offsets[i]=m.start()
  def get(i):
   pos=offsets[i];return mm[pos:mm.find(b';',pos)+1]
  todo=[root];seen=set();verts=[];cyls=[]
  while todo:
   i=todo.pop()
   if i in seen:continue
   seen.add(i);s=get(i)
   refs=[int(x) for x in re.findall(rb'#(\d+)',s.split(b'=',1)[1])]
   if b'VERTEX_POINT(' in s:
    point=get(refs[0]);v=re.search(rb'\(([-+\d.Ee]+),([-+\d.Ee]+),([-+\d.Ee]+)\)',point)
    if v:verts.append([float(x) for x in v.groups()])
   if b'CYLINDRICAL_SURFACE(' in s:
    placement=get(refs[0]);ptid=int(re.findall(rb'#(\d+)',placement.split(b'=',1)[1])[0]);point=get(ptid)
    v=re.search(rb'\(([-+\d.Ee]+),([-+\d.Ee]+),([-+\d.Ee]+)\)',point)
    radius=float(re.search(rb',([-+\d.Ee]+)\);',s)[1])
    if v:cyls.append({'center':[float(x) for x in v.groups()],'radius':radius})
   todo.extend(refs)
  mins=[min(v[k] for v in verts) for k in range(3)];maxs=[max(v[k] for v in verts) for k in range(3)]
  out[name]={'source':'PCB first Dielectric solid; vertex bounds in part coordinates; not assembled component envelope','root':root,'min':mins,'max':maxs,'size':[maxs[k]-mins[k] for k in range(3)],'cylinders':[c for c in cyls if c['radius']>1.4],'vertex_count':len(verts)}
  print(name, 'outline:', out[name]['size'][:2], flush=True)
 Path('design/enclosure/hippo-v0/reference-measurements.json').write_text(json.dumps(out,indent=2))
