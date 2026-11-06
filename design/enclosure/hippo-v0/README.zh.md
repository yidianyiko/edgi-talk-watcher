# 张嘴小河马 · V0 试装版

2026-10-23。用户确定：裸 Edgi Talk 板卡，无原壳；桌面摆放；Ender-3；交付 STL。整块屏幕放进张开的河马嘴中，USB 摄像头放在双眼之间。外观为淡紫河马、粉色嘴唇、米白牙齿，可单喷头分件分色打印。

**当前是可导出的机械试装原型，未完成实物配合或切片验证。建议先打印 `fit_frame.stl` 和 `board_template.stl`，通过后再打印整壳。** STL 网格通过不等于屏幕、接口、镜头、散热、麦克风或扬声器已验收。

## 数据来源与假设

| 项目 | 数据 / 状态 |
| --- | --- |
| 官方成品外形 | 115 × 73 × 20 mm，4.3 英寸屏幕；这是成品参考，不能代替裸板尺寸 |
| 实际底板模型 | 仓库 `vendor/edgi-talk-bsp/docs/3d model/PSoc_Edge_Basic_Model.zip` 内 `basic.stp`；PCB 轮廓约 110 × 69 mm |
| 底板安装孔 | STEP 中圆柱面半径约 2.075 mm；四角孔中心相对板左下角约 (4,4)、(106,4)、(4,65)、(106,65)，中心距 102 × 61 mm |
| 核心板轮廓 | `PSoc_Edge_Core_Model.zip` 内 `core.stp`，约 45 × 35 mm |
| STEP 提取边界 | `reference-measurements.json` 只描述 PCB 第一层介质实体的轮廓与圆柱面；其中 0.2032 mm 是单层厚度，**不是整块 PCB 厚度**；未提取完整元件包络 |
| 屏幕 | BSP 驱动命名 TL043WVV02，公开检索未取得这一准确型号的机械图；不以相近型号替代。玻璃外形、显示区偏置、厚度、排线与固定方式均待试装核实 |
| 摄像头基准 | INNOMAKER U20CAM-720P，PCB 32 × 32 mm，4 个直径 2.2 mm 孔，UVC / USB2.0，支持 320 × 240 YUY2；孔距、镜头突出高度未取得准确图纸，未在本板实测 |
| 当前屏幕开口 | 112 × 70 mm，圆角 2 mm，**设计假设**；预览中的 110 × 69 × 3 mm 深色块仅作比例占位，不是屏幕模型 |
| 摄像头固定 | 32.6 mm 方形容纳腔 + 扎带固定，避免猜测 PCB 孔距；前壳有独立托架固定柱；镜头中心开孔直径 22 mm |

来源：[RT-Thread 官方产品页](https://www.crowdsupply.com/rt-thread/edgi-talk)、[摄像头厂家规格](https://www.inno-maker.com/product/u20cam-720p/)、[Ender-3 官方打印范围](https://www.crealityofficial.co.uk/products/creality-ender-3-3d-printer)。摄像头协议和输出格式与当前采集路径匹配，仍不构成实际兼容性验证。

## 文件与数量

| STL | 数量 | 颜色 / 用途 |
| --- | --- | --- |
| fit_frame | 1 | 首先打印，1.2 mm 厚屏幕开口试装框 |
| board_template | 1 | 首先打印，110 × 69 mm 轮廓与四角孔位模板 |
| front | 1 | 紫色，前面板与侧壳一体，约 154 × 154 × 47 mm |
| back | 1 | 紫色，3 mm 后盖，含散热槽和后出线孔 |
| lip | 1 | 粉色，嘴唇 |
| muzzle | 1 | 浅紫色，宽鼻吻；背面有嘴唇和牙齿让位 |
| nostril | 2 | 深紫 / 黑色，鼻孔盖片 |
| tooth | 4 | 米白色，放在显示开口之外 |
| eye / pupil | 各 2 | 米白 / 黑色 |
| ear_inner | 2 | 粉色 |
| foot | 2 | 紫色，宽底脚，滑入机身前后方向的浅槽 |
| camera_tray | 1 | 内部摄像头托架，可替换 |
| spacer | 4 | 内部板卡支撑柱，22 mm 是试装初值，需按屏幕与元件包络调整 |

所有导出 STL 均为毫米语义，单件平放 Z=0；STL 本身不携带单位，切片软件按毫米、100% 比例导入。数量大于 1 的零件在切片软件复制。不要整套一次铺满平台；前壳、后盖分别打印。模型整体是固定张嘴，没有活动下颌。装配示意总体外接尺寸约为宽 154 × 高 162 × 深 78 mm（含底脚与装饰）。

## Ender-3 首版建议

- 默认按 0.4 mm 喷嘴、PLA、0.20 mm 层高、3–4 圈壁、15–20% 填充起步；温度和速度使用自己的耗材及打印机已校准配置。
- 维持导出方向，前壳面板贴平台、空腔向上；其余零件平底贴平台。设计意图是免支撑，侧边服务口有约 20 mm 跨桥，实际能否直接桥接需由切片预览和打印能力确认；必要时局部支撑。
- 前壳和后盖最大 XY 均约 154 × 154 mm，脚为 38 × 78 mm；名义上放得进 220 × 220 mm 平台，但切片时仍应核对裙边、底边和夹子位置。
- 装饰件用少量适合 PLA 的胶固定，先试摆再粘。底脚槽的总间隙设计为 0.8 mm，需要实际试配；可粘接固定并贴防滑垫。
- 前后壳用四颗 M3 螺钉；后盖通孔 3.4 mm、前壳试验导孔 2.8 mm，需先试验塑料咬合方式，勿直接强拧。固定板卡使用四角孔、垫圈与独立支撑柱，不压元件、屏幕玻璃或排线。螺钉长度需按实际啮合深度选择，不可顶到板卡。

## 试装与装配顺序

1. 打印两块薄模板。板卡模板应对齐真实底板四角孔；屏幕试装框应能露出完整显示和触控区，边框只接触非显示边缘。若开口不合适，修改 `window_w/window_h/board_y` 后重新导出薄框。
2. 核实屏幕现有固定方式、玻璃外形、排线弯曲空间和整个板卡叠层深度。当前模型没有可靠的屏幕压框与排线夹持设计，不能依靠后盖硬压屏幕；这一步未通过前不装机通电。
3. 试摆板卡与摄像头，调整支撑柱高度。CAD 的板卡示例是后盖内表面 Z=47、22 mm 支撑柱伸向前方，板卡接触面约 Z=25；不是已确认的板卡位置。
4. 摄像头托架装配预览放在 Z=12，镜头朝向前面；用扎带轻固定 PCB，托架孔与前壳柱位置对应，必要时加垫片或调整柱高。镜头前端需接近或略突出前面板，实测画面四角无暗角，鼻吻及嘴唇不进入视野。此处不承诺现选镜头高度已经合适。
5. USB 线接板卡 host，供电/调试线从左侧大服务口或后孔引出。侧口是覆盖范围较大的试装开口，不是依据真实插头完成的精确接口孔；确认连接器与电缆弯曲空间后再收窄。声孔、天线空间也需按实板确认。
6. 空壳试配后再安装装饰件与底脚，最后接线、合盖。检查桌面稳定性、触控边缘可达性、相机遮挡、温升和音频开孔效果。

首版没有电池仓，也没有改变产品现有供电方式。

## 复现与检查

本次用 OpenSCAD 2021.01 导出，trimesh 5.1.1 检查。可用任意合适 Python 环境安装 trimesh / numpy；本次依赖环境位于 `/tmp/rt-enclosure-venv`，不属于长期项目依赖。

```sh
QT_QPA_PLATFORM=offscreen python3 design/enclosure/hippo-v0/export.py
PYTHONPATH=/tmp/rt-enclosure-venv/lib/python3.12/site-packages python3 design/enclosure/hippo-v0/verify_meshes.py
QT_QPA_PLATFORM=offscreen PYTHONPATH=/tmp/rt-enclosure-venv/lib/python3.12/site-packages python3 design/enclosure/hippo-v0/check_clearances.py
```

`mesh-report.json` 检查全部 STL 封闭性、法线一致性、正体积、单连通体、Z=0 和名义打印包络；`clearance-report.json` 检查选定装配实体之间无体积重叠。零厚度接触面在 CGAL 中可能输出非流形提示，在 trimesh 中可能产生零体积质心警告；检查明确以交集体积为准，这些接触面不是交付 STL。`*.build.log`、`*.clearance.log` 保留本次输出。`preview.png` / `preview-angle.png` 来自实际 SCAD 装配模型，不是 AI 效果图。

STEP 数据复现：先将两份官方 ZIP 解压为 `/tmp/rt-enclosure-reference/basic.stp` 和 `core.stp`，在仓库根目录执行 `python3 design/enclosure/hippo-v0/inspect_reference.py`。提取器读取选定介质层实体的顶点和圆柱面，不处理全装配元件包络，也不做任意 STEP 文件的通用测量。
