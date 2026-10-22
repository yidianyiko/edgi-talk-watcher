"""Rebuild a labeled historical presentation from allowlisted, existing evidence."""
from pathlib import Path
import hashlib
import json
import subprocess
import zipfile

from PIL import Image, ImageDraw, ImageFont

ROOT = Path(__file__).resolve().parents[2]
OUT = ROOT / 'artifacts/submission'
DOCS = ROOT / 'docs/submission'
FONT = '/usr/share/fonts/truetype/dejavu/DejaVuSans.ttf'
BOLD = '/usr/share/fonts/truetype/dejavu/DejaVuSans-Bold.ttf'
SOURCES = {
    'event_before': 'artifacts/product-completion/recorded/hand-removal/events/1/before.jpg',
    'event_after': 'artifacts/product-completion/recorded/hand-removal/events/1/after.jpg',
    'board_1': 'artifacts/board-camera/board-frame-1.jpg',
    'board_2': 'artifacts/board-camera/board-frame-2.jpg',
    'screen': 'artifacts/board-face/screen-still.png',
}


def font(size, bold=False):
    return ImageFont.truetype(BOLD if bold else FONT, size)


def canvas(title, label):
    im = Image.new('RGB', (1280, 720), '#101b2a')
    d = ImageDraw.Draw(im)
    d.text((56, 35), title, font=font(37, True), fill='#e6f3ff')
    d.text((56, 94), label, font=font(20), fill='#5de2d2')
    d.line((56, 132, 1224, 132), fill='#304456', width=2)
    d.text((56, 673), 'WATCHER  |  RT-Thread / Edgi Talk  |  Historical evidence presentation',
           font=font(18), fill='#99adbf')
    return im, d


def text(d, lines, x=60, y=180, size=29, step=56):
    for line in lines:
        d.text((x, y), line, font=font(size), fill='#e6f3ff')
        y += step


def photo(im, key, box):
    with Image.open(ROOT / SOURCES[key]) as source:
        src = source.convert('RGB')
    src.thumbnail((box[2] - box[0], box[3] - box[1]))
    im.paste(src, (box[0] + (box[2]-box[0]-src.width)//2,
                   box[1] + (box[3]-box[1]-src.height)//2))


def main():
    OUT.mkdir(parents=True, exist_ok=True)
    slides = []
    im, d = canvas('WATCHER: one instruction, one visual task',
                   'Preserved evidence through V8 / 2026-10-21. Silent, captioned presentation.')
    text(d, ['Watch for one target appearing or disappearing.',
             'Keep before/after images when a new event occurs.',
             'Board: camera, microphone, Wi-Fi, display, alert control.',
             'Host: local ASR, existing Jev model, persistent history.',
             'No custom target-specific model training.'], size=28, step=72)
    slides.append(im)

    im, d = canvas('Voice control and system boundaries',
                   'Architecture explanation. This slide is not a recording of a live interaction.')
    text(d, ['Six-second board recording -> authenticated Wi-Fi upload',
             'Local Whisper ASR -> task / pause / continue',
             'Camera frames -> validated task -> Jev -> event history',
             'At V8: daily voice launcher still selected the PC camera.',
             'Board-camera uploads were tested on a separate path.',
             'Later integration requires its own acceptance evidence.'], size=26, step=65)
    slides.append(im)

    im, d = canvas('A hand disappears: one archived event',
                   'ACTUAL PC-camera images / saved recording evaluation / held stills, not live video')
    photo(im, 'event_before', (55, 170, 620, 510))
    photo(im, 'event_after', (660, 170, 1225, 510))
    d.text((58, 535), 'BEFORE: hand visible', font=font(23), fill='#e6f3ff')
    d.text((660, 535), 'AFTER: hand absent', font=font(23), fill='#e6f3ff')
    d.text((58, 590), 'One alert; confidence 1.0. Later empty frames: uncertain.',
           font=font(23), fill='#5de2d2')
    slides.append(im)

    im, d = canvas('Physical board camera -> Wi-Fi -> model',
                   'ACTUAL board-camera captures / 320x240 YUYV converted to JPEG / held stills')
    photo(im, 'board_1', (55, 165, 620, 530))
    photo(im, 'board_2', (660, 165, 1225, 530))
    text(d, ['Two real uploads; one Jev decision: uncertain; no event.',
             'This verifies the bounded transport path, not event accuracy.'],
         x=58, y=560, size=25, step=45)
    slides.append(im)

    im, d = canvas('A face on the screen, with explicit status',
                   'ACTUAL board framebuffer readback / offline pose / not an external screen video')
    photo(im, 'screen', (70, 155, 390, 645))
    text(d, ['Two eyes reflect the device state.',
             'Task, event count and controls stay visible.',
             'Blink and gaze animation exists in firmware.',
             'This still does not demonstrate physical touch.',
             'PLAY/DONE is not proof of audible output.'],
         x=440, y=205, size=25, step=72)
    slides.append(im)

    im, d = canvas('Repeatable tests; honest remaining boundaries',
                   'Saved frames and responses support debugging without repeated human participation.')
    text(d, ['Archived evaluation: 678 JPEGs, 67 real decisions.',
             'Two event alerts; occlusion returned uncertain.',
             'No claim of full-frame evaluation or 24h reliability.',
             'No synthetic sound presented as a board speaker recording.',
             'Inference and persistent storage still require a host.',
             'Local package prepared; no public submission receipt.'], size=26, step=65)
    slides.append(im)

    for i, slide in enumerate(slides):
        slide.save(OUT / f'slide-{i+1:02}.png')
    concat = OUT / 'slides.txt'
    concat.write_text(''.join(f"file 'slide-{i+1:02}.png'\nduration 10\n" for i in range(len(slides)))
                      + f"file 'slide-{len(slides):02}.png'\n")
    subprocess.run(['ffmpeg', '-hide_banner', '-loglevel', 'error', '-y',
                    '-f', 'concat', '-safe', '0', '-i', str(concat), '-t', '60',
                    '-vf', 'fps=24,format=yuv420p', '-c:v', 'libx264',
                    '-preset', 'medium', '-crf', '21', '-movflags', '+faststart',
                    '-an', str(OUT/'demo.mp4')], check=True)
    probe = json.loads(subprocess.check_output(['ffprobe', '-v', 'error', '-show_streams',
                                               '-show_format', '-of', 'json', str(OUT/'demo.mp4')]))
    assert len(probe['streams']) == 1
    stream = probe['streams'][0]
    assert stream['codec_type'] == 'video' and stream['codec_name'] == 'h264'
    assert (stream['width'], stream['height']) == (1280, 720)
    assert float(probe['format']['duration']) == 60.0
    subprocess.run(['ffmpeg', '-v', 'error', '-i', str(OUT/'demo.mp4'),
                    '-f', 'null', '-'], check=True)
    sha = lambda p: hashlib.sha256(p.read_bytes()).hexdigest()
    manifest = {
        'created_on': '2026-10-22',
        'evidence_checkpoint': 'V8 board camera / V7 screen readback / prior PC-camera event',
        'media_kind': 'silent captioned presentation; six static slides held ten seconds each',
        'live_or_full_motion': False,
        'source_files': [{'path': path, 'sha256': sha(ROOT/path)} for path in SOURCES.values()],
        'video': {'path': 'artifacts/submission/demo.mp4', 'duration_seconds': 60,
                  'width': 1280, 'height': 720, 'codec': 'h264', 'audio_streams': 0,
                  'sha256': sha(OUT/'demo.mp4')},
        'decode_check': 'ffmpeg complete decode exited 0',
    }
    (OUT/'media-manifest.json').write_text(json.dumps(manifest, indent=2)+'\n')
    allowed = [DOCS/n for n in ['README.md', 'quickstart.en.md', 'forum-draft.zh.md',
                               'submission-checklist.md', 'submission-fields.json', 'build_demo.py',
                               'source-build-notes.en.md', 'build_source_release.py']]
    allowed += [ROOT/'docs/board-camera-integration.md', ROOT/'artifacts/board-integration/acceptance-report.json', OUT/'demo.mp4', OUT/'media-manifest.json']
    with zipfile.ZipFile(OUT/'package.zip', 'w', zipfile.ZIP_DEFLATED) as archive:
        for path in allowed:
            archive.write(path, path.relative_to(ROOT))
    with zipfile.ZipFile(OUT/'package.zip') as archive:
        assert archive.testzip() is None
        assert len(archive.namelist()) == len(allowed)
        assert not any('.env' in n or 'token' in n for n in archive.namelist())
    print(json.dumps({'video_duration': probe['format']['duration'],
                      'video_streams': len(probe['streams']), 'archive_entries': len(allowed),
                      'package_bytes': (OUT/'package.zip').stat().st_size,
                      'package_sha256': sha(OUT/'package.zip'), 'decode': 'pass'}, indent=2))


if __name__ == '__main__':
    main()
