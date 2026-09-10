"""Run the real local Git rehearsal and present its evidence as a 30-second GIF.

This is a paced visualization of captured results, not a screen recording or a
measurement of migration duration. Pillow is an optional authoring dependency;
the comparator and its normal test suite remain standard-library-only.
"""
import argparse
import hashlib
import json
from pathlib import Path
import platform
import shutil
import subprocess
import sys
import tempfile

from PIL import Image, ImageDraw, ImageFont, __version__ as pillow_version

# Resolve the project relative to this script so invocation does not depend on
# the caller's current directory. The imported harness owns disposable repos.
ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT))
import rehearse_refs
import verify_refs

WIDTH, HEIGHT = 1200, 720
DURATIONS = [7000, 8000, 8000, 7000]
BG, PANEL, WHITE = '#101923', '#192632', '#edf4fa'
MUTED, GREEN, AMBER, LINE = '#a9bdce', '#71e2bd', '#ffcb80', '#304557'


def font(size, bold=False):
    """Use local fonts without fetching assets; retain a portable fallback."""
    name = 'DejaVuSansMono-Bold.ttf' if bold else 'DejaVuSansMono.ttf'
    for path in (Path('/usr/share/fonts/truetype/dejavu') / name,
                 Path('C:/Windows/Fonts') / ('consolab.ttf' if bold else 'consola.ttf')):
        if path.is_file():
            return ImageFont.truetype(str(path), size)
    return ImageFont.load_default(size=size)


def text(draw, xy, value, size=24, color=WHITE, bold=False):
    """Fail on horizontal overflow instead of publishing clipped evidence."""
    face = font(size, bold)
    if draw.textbbox(xy, value, font=face)[2] > WIDTH - 44:
        raise ValueError(f'Text exceeds the demo canvas: {value}')
    draw.text(xy, value, font=face, fill=color)


def frame(step, title, subtitle):
    image = Image.new('RGB', (WIDTH, HEIGHT), BG)
    draw = ImageDraw.Draw(image)
    text(draw, (48, 28), 'GITHUB MIGRATION READINESS', 20, GREEN, True)
    text(draw, (1030, 28), f'{step} / 4', 20, MUTED)
    text(draw, (48, 84), title, 38, bold=True)
    text(draw, (48, 145), subtitle, 23, MUTED)
    draw.rounded_rectangle((40, 205, 1160, 585), radius=16, fill=PANEL)
    text(draw, (48, 624), 'Actual local Git results / synthetic repositories', 22, MUTED)
    text(draw, (48, 664), 'Paced playback; not elapsed runtime. Full evidence linked below.', 19, MUTED)
    return image, draw


def make_frames(evidence, matching, broken, source, destination):
    """Use observed counts, exit codes and IDs for every displayed result.

    The storyboard describes the harness's fixed synthetic scenario. Explicit
    checks stop it if that scenario changes and its editorial labels go stale.
    """
    observations = {item['scenario']: item for item in evidence['observations']}
    findings = {item['ref']: item for item in broken['findings']}
    expected = {'refs/heads/feature': 'missing', 'refs/heads/destination-only': 'unexpected',
                'refs/heads/main': 'mismatched', 'refs/tags/v1.0.0': 'mismatched'}
    if {key: item['status'] for key, item in findings.items()} != expected:
        raise ValueError('Rehearsal findings changed; review the storyboard before rendering.')
    tag, peeled = 'refs/tags/v1.0.0', 'refs/tags/v1.0.0^{}'
    if source[peeled] != destination[peeled] or source[tag] == destination[tag]:
        raise ValueError('The annotation-only change no longer matches this storyboard.')
    if not evidence['source_unchanged'] or matching['status'] != 'match':
        raise ValueError('The intact-copy or source-preservation check did not pass.')

    frames = []
    image, draw = frame(1, 'First, verify an intact copy.', 'Compare every advertised branch and tag record.')
    text(draw, (72, 238), 'INTACT COPY', 23, MUTED)
    text(draw, (72, 288), matching['status'].upper(), 54, GREEN, True)
    text(draw, (72, 378), f"{matching['counts']['matched']} matched records", 32)
    text(draw, (72, 443), 'Two branches + lightweight tag + annotated tag + peeled target', 22)
    text(draw, (72, 514), f"Comparator exit: {observations['matching']['exit_code']}", 25, GREEN)
    frames.append(image)

    image, draw = frame(2, 'Then, change the disposable copy.', 'The comparator identifies each difference by ref name.')
    for index, (ref, status) in enumerate(expected.items()):
        y = 242 + index * 61
        text(draw, (72, y), findings[ref]['status'].upper(), 23, AMBER, True)
        text(draw, (304, y), ref, 24)
    text(draw, (72, 514), f"Comparator exit: {observations['broken']['exit_code']}  /  {len(findings)} differences found", 25, AMBER)
    frames.append(image)

    image, draw = frame(3, 'Same target. Different annotation.', 'Checking only the target commit would miss this changed tag.')
    text(draw, (72, 237), tag, 26, WHITE, True)
    text(draw, (72, 292), f'Source object       {source[tag][:12]}', 26)
    text(draw, (72, 341), f'Destination object  {destination[tag][:12]}', 26, AMBER)
    draw.line((72, 399, 1128, 399), fill=LINE, width=2)
    text(draw, (72, 432), f'Both peeled targets {source[peeled][:12]}', 26, GREEN)
    text(draw, (72, 511), 'Tag object: MISMATCHED / peeled target: MATCHED', 24)
    frames.append(image)

    image, draw = frame(4, 'Keep the evidence. Review the gaps.', 'Intact copy matched; the changed copy returned differences.')
    for index, key in enumerate(('matched', 'missing', 'unexpected', 'mismatched')):
        x = 72 + index * 270
        text(draw, (x, 243), str(broken['counts'][key]), 52, GREEN if key == 'matched' else AMBER, True)
        text(draw, (x, 319), key.upper(), 22, MUTED)
    text(draw, (72, 404), f"Source refs unchanged: {str(evidence['source_unchanged']).lower()}", 25, GREEN)
    text(draw, (72, 464), 'JSON + Markdown reports retain full IDs and input hashes.', 23)
    text(draw, (72, 518), 'Ref equality is one check, not complete migration acceptance.', 22)
    frames.append(image)
    return frames


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--output-dir', type=Path, required=True, help='New directory for visuals and evidence')
    args = parser.parse_args()
    try:
        if args.output_dir.exists():
            raise ValueError('Choose a new output directory; existing evidence is never overwritten.')
        with tempfile.TemporaryDirectory(prefix='ref-demo-render-') as folder:
            working = Path(folder) / 'rehearsal'
            evidence = rehearse_refs.run_demo(working)
            matching = json.loads((working / 'matching/refs.json').read_text(encoding='utf-8'))
            broken = json.loads((working / 'broken/refs.json').read_text(encoding='utf-8'))
            source = verify_refs.parse_snapshot((working / 'source.refs').read_bytes(), 'source')
            destination = verify_refs.parse_snapshot((working / 'broken.refs').read_bytes(), 'destination')
            frames = make_frames(evidence, matching, broken, source, destination)
            args.output_dir.mkdir(parents=True, exist_ok=False)
            shutil.copytree(working, args.output_dir / 'evidence')

        # Four held frames avoid simulated terminal typing or invented timings.
        # Omitting the GIF loop extension plays once in conforming viewers. A
        # static final frame and textual transcript provide motion-free access.
        frames[0].save(args.output_dir / 'demo.gif', save_all=True, append_images=frames[1:],
                       duration=DURATIONS, disposal=2, optimize=True)
        frames[-1].save(args.output_dir / 'summary.png', optimize=True)
        transcript = ('# Ref verification demo: text version\n\n'
            'This 30-second presentation visualizes an actual run against disposable synthetic Git repositories. '
            'It is not a screen recording or measured migration duration.\n\n'
            f"1. Intact copy: {matching['counts']['matched']} matched records; comparator exit 0.\n"
            f"2. Changed copy: {len(broken['findings'])} differences; comparator exit 1.\n"
            '3. The annotated tag object changed while its peeled target stayed identical. '
            'The visual abbreviates IDs to 12 characters; full IDs are retained below.\n'
            '4. Source refs remained unchanged. Matching refs alone does not certify a migration.\n\n'
            '[Intact report](evidence/matching/refs.md) · [Execution evidence](evidence/evidence.json)\n\n'
            + verify_refs.markdown(broken))
        (args.output_dir / 'transcript.md').write_text(transcript, encoding='utf-8')
        files = [path for path in args.output_dir.rglob('*') if path.is_file()]
        manifest = {'presentation_seconds': sum(DURATIONS) / 1000, 'frame_durations_ms': DURATIONS,
                    'observed_at': evidence['observed_at'], 'python': platform.python_version(),
                    'pillow': pillow_version, 'git': rehearse_refs.git(ROOT, '--version'),
                    'source_sha256': {name: hashlib.sha256((ROOT / name).read_bytes()).hexdigest()
                                      for name in ('verify_refs.py', 'rehearse_refs.py', 'tools/render_ref_demo.py')},
                    'file_sha256': {path.relative_to(args.output_dir).as_posix(): hashlib.sha256(path.read_bytes()).hexdigest()
                                    for path in sorted(files)}}
        (args.output_dir / 'manifest.json').write_text(json.dumps(manifest, indent=2) + '\n', encoding='utf-8')
        print(json.dumps({'result': 'passed', 'output_dir': str(args.output_dir), 'frames': len(frames),
                          'presentation_seconds': sum(DURATIONS) / 1000}))
        return 0
    except (OSError, ValueError, RuntimeError, subprocess.TimeoutExpired) as error:
        print(f'Ref demo rendering failed: {error}', file=sys.stderr)
        return 2


if __name__ == '__main__':
    sys.exit(main())
