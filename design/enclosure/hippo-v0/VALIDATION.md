# V0 verification, 2026-10-23

- `QT_QPA_PLATFORM=offscreen python3 design/enclosure/hippo-v0/export.py`: 14 named parts exported; each process exited 0, logs included.
- `verify_meshes.py` with numpy 2.3.1 / trimesh 5.1.1: 14 / 14 PASS. All individual meshes are closed, consistently wound, positive volume, one connected component, Z=0, and inside the nominal Ender-3 envelope.
- `check_clearances.py`: 6 / 6 selected pair checks PASS; nominal volumetric intersections are zero. Mating zero-thickness surfaces are allowed. Checks cover lip/muzzle, upper teeth/muzzle, camera tray/shell, feet/shell, feet/lip, front/back.
- `preview.png` and `preview-angle.png`: exported by OpenSCAD from the same `hippo.scad` assembly and visually inspected.
- Independent source review found lip/muzzle overlap and an undersized camera cavity. Source corrected, affected STLs rebuilt, reports regenerated.

Not performed: slicer/toolpath verification; actual printer run; actual bare-board/screen/camera fit; exact screen mechanical measurements; camera electrical compatibility on the board; loaded stability, thermal/audio or optical acceptance. The PCB reference measurements do not establish the complete mounted component envelope. This is a fit-check prototype, not a validated finished enclosure.
