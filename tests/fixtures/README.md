# tests/fixtures — the few real bytes the suite cannot synthesise

Almost every test here builds what it needs from `rulebase.make()`: a record
drawn in-process is cheaper than a file, and it cannot go stale. These are the
exceptions — the handful of tests that need bytes a renderer actually wrote.

| fixture | used by | why a real file is needed |
| --- | --- | --- |
| `images/{synthdog,html,genalog}/*.jpg` | `test_invariants.py`, `test_drift.py` | `invariants.jpeg_size()` parses a JPEG header, and `drift.shard_vector()` averages real pixel counts. A synthesised file proves neither. |
| `ocr/aged_report.json`, `ocr/clean_report.json` | `test_ocr_proof.py` | Re-aggregating a real run's per-image scores under a different layout mix is the exact situation the scoring code exists to survive. |

One render per renderer, two for `html` so the pixel mean is taken over more
than one value. They came out of a `make dataset` run and are kept here, rather
than in a committed dataset, so the suite stays green without 36 MB of generated
images in git.

Refresh them after a change that alters what the renderers write:

```bash
make dataset N=2
cp data/dataset60/html/html_00{0,1}.jpg   tests/fixtures/images/html/
cp data/dataset60/synthdog/synthdog_000.jpg tests/fixtures/images/synthdog/
cp data/dataset60/genalog/genalog_000.jpg   tests/fixtures/images/genalog/
make proof DATASET=data/dataset60
cp data/dataset60/proof/ocr_report.json tests/fixtures/ocr/aged_report.json
```
