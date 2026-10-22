"""Preserve original camera samples and export review videos; never records a camera."""
import argparse
import hashlib
import json
from pathlib import Path
import shutil
import subprocess

ROOT = Path(__file__).resolve().parents[1]
SOURCES = {
    'hand-removal': 'artifacts/object-watch/hand-removal-live',
    'person-arrival': 'artifacts/continuous/uncovered-five-minutes',
    'occlusion': 'artifacts/continuous/five-minutes-v2',
}


def digest(path):
    return hashlib.sha256(path.read_bytes()).hexdigest()


def archive(source, target):
    target.mkdir(parents=True, exist_ok=False)
    frames = target/'frames'
    frames.mkdir()
    index = []
    for meta in sorted((source/'frames').glob('*.json')):
        item = json.loads(meta.read_text())
        image = source/item['path']
        if image.resolve().parent != (source/'frames').resolve():
            raise ValueError('Unexpected source frame path')
        if index and item['time'] <= index[-1]['time']:
            raise ValueError('Source timestamps must increase')
        shutil.copy2(image, frames/image.name)
        shutil.copy2(meta, frames/meta.name)
        index.append({**item, 'sha256': digest(image), 'metadata_sha256': digest(meta)})
    if not index:
        raise ValueError('No recorded frames')
    # Preview is deliberately one sampled frame per second, NOT full-rate original footage.
    subprocess.run(['ffmpeg', '-hide_banner', '-loglevel', 'error', '-n',
                    '-framerate', '1', '-i', str(frames/'%06d.jpg'),
                    '-c:v', 'libx264', '-preset', 'fast', '-crf', '18',
                    '-pix_fmt', 'yuv420p', '-movflags', '+faststart', str(target/'preview.mp4')],
                   check=True, timeout=180)
    probe = json.loads(subprocess.check_output([
        'ffprobe', '-v', 'error', '-count_frames', '-show_entries',
        'stream=codec_name,width,height,nb_read_frames:format=duration',
        '-of', 'json', str(target/'preview.mp4')], text=True))
    if int(probe['streams'][0]['nb_read_frames']) != len(index):
        raise ValueError('Video frame count does not match preserved samples')
    subprocess.run(['ffmpeg', '-v', 'error', '-i', str(target/'preview.mp4'),
                    '-f', 'null', '-'], check=True, timeout=90)
    for name in ('run.json', 'summary.json', 'cleanup.json', 'camera-cleanup.json'):
        if (source/name).exists():
            shutil.copy2(source/name, target/name)
    manifest = {'schema_version': 1, 'source': str(source.relative_to(ROOT)),
                'kind': 'real_camera_sampled_frames', 'audio': False,
                'preview_fps': 1, 'preview_duration_seconds': float(probe['format']['duration']),
                'original_elapsed_seconds': index[-1]['time']-index[0]['time'],
                'note': 'Preview reconstructs one frame per second. Original capture timestamps in this index are authoritative; no full-rate video was recorded.',
                'frames': index, 'preview_sha256': digest(target/'preview.mp4')}
    (target/'recording.json').write_text(json.dumps(manifest, ensure_ascii=False, indent=2)+'\n')
    return {'id': target.name, 'frames': len(index), 'original_elapsed_seconds': manifest['original_elapsed_seconds'],
            'preview_sha256': manifest['preview_sha256']}


def verify(root):
    count = 0
    entries = json.loads((root/'index.json').read_text())
    if not isinstance(entries, list) or not entries:
        raise ValueError('No archive index entries')
    expected = {entry['id'] for entry in entries}
    actual = {path.parent.name for path in root.glob('*/recording.json')}
    if expected != actual or len(expected) != len(entries):
        raise ValueError('Missing, extra or duplicate recordings')
    for entry in entries:
        recording = root/entry['id']/'recording.json'
        meta = json.loads(recording.read_text())
        base = recording.parent
        if len(meta['frames']) != entry['frames'] or meta['preview_sha256'] != entry['preview_sha256']:
            raise ValueError('Recording disagrees with archive index')
        if digest(base/'preview.mp4') != meta['preview_sha256']:
            raise ValueError('Video checksum mismatch: '+base.name)
        for item in meta['frames']:
            image = base/item['path']
            if digest(image) != item['sha256'] or digest(image.with_suffix('.json')) != item['metadata_sha256']:
                raise ValueError('Frame checksum mismatch: '+str(image))
            count += 1
    if not count:
        raise ValueError('No archived recordings')
    return count


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--root', type=Path, default=ROOT/'testdata/recordings')
    parser.add_argument('--verify', action='store_true')
    args = parser.parse_args()
    if args.verify:
        print(f'Verified {verify(args.root)} original frames, metadata and video checksums')
        return
    args.root.mkdir(parents=True, exist_ok=False)
    results = [archive(ROOT/path, args.root/name) for name, path in SOURCES.items()]
    (args.root/'index.json').write_text(json.dumps(results, indent=2)+'\n')
    print(json.dumps(results))

if __name__ == '__main__':
    main()
