# Reproduce the visual ref-verification demo

The README's GIF presents results from an actual run of `rehearse_refs.py` against disposable, synthetic Git repositories. It is a paced visualization of captured output, not a terminal recording or a migration speed claim. The four frames last 7, 8, 8 and 7 seconds. The GIF has no repeat extension; viewers normally play it once and stop on the summary.

[Static summary](assets/ref-demo/summary.png) · [Text transcript](assets/ref-demo/transcript.md) · [Run evidence](assets/ref-demo/evidence/evidence.json) · [Source and asset hashes](assets/ref-demo/manifest.json)

## Run it without image dependencies

From the repository root with Git and Python 3.11 or later:

```shell
python rehearse_refs.py --output-dir reports/ref-demo-rehearsal
```

This generates the same comparison scenarios and reports without rendering images. Use a new output directory for each run. The intact copy returns comparator exit 0; the deliberately changed copy returns 1. The harness returns 0 only when both expected outcomes and unchanged source refs are confirmed.

## Render a new visual

Image authoring additionally needs Pillow. From the repository root:

```shell
python -m pip install -r tools/requirements-demo.txt
python tools/render_ref_demo.py --output-dir reports/ref-demo-preview
```

The script runs the local rehearsal itself, retains its captures and JSON/Markdown reports, and derives displayed counts, exit codes and object IDs from those files. It refuses an existing output directory and stops if the findings no longer match the storyboard. No existing repository is modified. Git network transports remain disabled by the rehearsal harness; installing Pillow may require network access.

Open `reports/ref-demo-preview/demo.gif`, `summary.png` and `transcript.md`. Inspect all four frames before publishing. Their order is intact match, four differences, annotation-only change and final summary. The source and destination tag IDs differ, while the peeled target matches. IDs in the visual are abbreviated to 12 characters; the retained captures and difference report contain full IDs.

`manifest.json` records the observed run time, Python/Pillow/Git versions, source-file hashes and generated-file hashes. Reproducing the demo runs Git again, so timestamps will differ. Fonts are selected locally: DejaVu Sans Mono on typical Linux hosts, Consolas on Windows, otherwise Pillow's default font. Different fonts or image-library versions may change pixels and file hashes without changing comparison results. Compare the reports when assessing behavior.

The renderer uses Pillow's [GIF sequence and timing options](https://pillow.readthedocs.io/en/stable/handbook/image-file-formats.html#gif). The optional authoring dependency does not change the comparator or its standard-library-only tests.

## Scope

The committed visual demonstrates two branches, a lightweight tag and an annotated tag with its peeled target. The altered copy has one missing branch, one destination-only branch, one moved branch and one changed tag annotation. It does not prove a hosted migration, complete object availability, LFS transfer, metadata preservation or production readiness. Follow the [full verification walkthrough](ref-verification.md) for collection requirements and remaining acceptance checks.
