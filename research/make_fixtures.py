"""Generate schematic smoke fixtures; never claim these represent camera accuracy."""
import json
from pathlib import Path
from PIL import Image, ImageDraw

ROOT = Path(__file__).resolve().parent / 'fixtures'


def scene(kind, present=True, color='red', distractor=False, obscured=False):
    im = Image.new('RGB', (640, 480), '#dddcd5')
    d = ImageDraw.Draw(im)
    d.rectangle((0, 330, 640, 480), fill='#b6a389')
    if kind == 'cup' and present:
        d.rounded_rectangle((240, 210, 340, 345), 12, fill='#2862b2')
        d.ellipse((310, 230, 390, 310), outline='#2862b2', width=15)
        d.ellipse((243, 205, 338, 230), fill='#112d58')
    if kind == 'parcel' and present:
        d.rectangle((220, 240, 410, 360), fill='#bd8547', outline='#62401e', width=4)
        d.rectangle((300, 240, 325, 360), fill='#e0bf86')
    if kind == 'indicator':
        d.rounded_rectangle((230, 180, 390, 350), 15, fill='#444444')
        d.ellipse((275, 220, 345, 290), fill=color)
    if distractor:
        d.ellipse((60, 270, 140, 350), fill='#e4bb20', outline='#343434', width=3)
    if obscured:
        d.rectangle((150, 100, 460, 400), fill='#111111')
    return im


def main():
    ROOT.mkdir(exist_ok=True)
    tasks = {
        'cup': 'Tell me when the blue cup that was on the table is removed.',
        'parcel': 'Tell me when a parcel appears on the empty table.',
        'indicator': 'Tell me when the device indicator changes from red to green.'}
    cases, thumbs = [], []
    for kind, task in tasks.items():
        for variation, expected in [('event', 'event'), ('unchanged', 'no_event'),
                                     ('distractor', 'no_event'), ('obscured', 'uncertain')]:
            case_id = kind + '_' + variation
            before = scene(kind, present=kind != 'parcel')
            after = scene(kind, present=(kind != 'cup' if variation == 'event' else kind != 'parcel'),
                          color='green' if kind == 'indicator' and variation == 'event' else 'red',
                          distractor=variation == 'distractor', obscured=variation == 'obscured')
            frames = []
            for index, im in enumerate([before, after]):
                name = f'{case_id}_{index}.png'
                im.save(ROOT / name)
                frames.append({'path': name, 'seconds_ago': 2 if index == 0 else 0})
            cases.append({'id': case_id, 'task': task, 'expected': expected, 'frames': frames})
            thumb = after.resize((256, 192))
            tile = Image.new('RGB', (256, 218), 'white')
            tile.paste(thumb, (0, 26))
            ImageDraw.Draw(tile).text((5, 5), case_id, fill='black')
            thumbs.append(tile)
    sheet = Image.new('RGB', (1024, 654), 'white')
    for i, thumb in enumerate(thumbs):
        sheet.paste(thumb, ((i % 4) * 256, (i // 4) * 218))
    sheet.save(ROOT / 'contact-sheet.png')
    (ROOT / 'manifest.json').write_text(json.dumps({'fixture_kind': 'synthetic_schematic', 'cases': cases}, indent=2) + '\n')
    print(f'Generated {len(cases)} synthetic cases in {ROOT}')


if __name__ == '__main__':
    main()
