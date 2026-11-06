"""Export independently printable pieces with OpenSCAD 2021.01+."""
from concurrent.futures import ThreadPoolExecutor
from pathlib import Path
import subprocess
ROOT=Path(__file__).resolve().parent
PARTS=['front','back','lip','muzzle','nostril','tooth','eye','pupil','ear_inner','spacer','camera_tray','foot','fit_frame','board_template']
def export(part):
 p=subprocess.run(['openscad','--hardwarnings','--export-format','binstl','-D',f'part="{part}"','-o',str(ROOT/f'{part}.stl'),str(ROOT/'hippo.scad')],capture_output=True,text=True)
 (ROOT/f'{part}.build.log').write_text(p.stdout+p.stderr)
 if p.returncode:raise RuntimeError(part+': '+p.stderr)
 print(part,'EXPORTED',flush=True)
if __name__=='__main__':
 with ThreadPoolExecutor(max_workers=2) as pool:list(pool.map(export,PARTS))
