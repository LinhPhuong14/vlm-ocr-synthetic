# Where the time goes

Measured by `tools/profile_pipeline.py`. Every stage is timed, including the ones nobody suspects; the interpreter start-up a child process cannot see is measured from outside and named, so the column adds up to the wall clock rather than to most of it.

## Per stage, per renderer

| stage | synthdog s | synthdog % | html s | html % | genalog s | genalog % |
| --- | ---: | ---: | ---: | ---: | ---: | ---: |
| interpreter | 1.184 | 5.7% | 0.242 | 2.2% | 0.933 | 12.6% |
| startup | 0.008 | 0.0% | 0.616 | 5.6% | 0.000 | 0.0% |
| sampling | 0.561 | 2.7% | 0.566 | 5.1% | 0.627 | 8.5% |
| content | 0.004 | 0.0% | 0.004 | 0.0% | 0.004 | 0.1% |
| layout | 0.039 | 0.2% | 0.039 | 0.4% | 0.039 | 0.5% |
| render | 4.895 | 23.4% | 5.116 | 46.3% | 1.739 | 23.5% |
| scene | 10.172 | 48.6% | 0.000 | 0.0% | 0.000 | 0.0% |
| geometry | 0.003 | 0.0% | 0.173 | 1.6% | 0.005 | 0.1% |
| degradation | 3.917 | 18.7% | 4.222 | 38.2% | 3.961 | 53.6% |
| annotation | 0.004 | 0.0% | 0.002 | 0.0% | 0.003 | 0.0% |
| validation | 0.002 | 0.0% | 0.002 | 0.0% | 0.003 | 0.0% |
| export | 0.108 | 0.5% | 0.067 | 0.6% | 0.068 | 0.9% |
| *unattributed* | 0.023 | 0.1% | 0.003 | 0.0% | 0.005 | 0.1% |

`interpreter` and `startup` are paid once per process, not per image, so their share shrinks as a run gets longer; every other row scales with the image count.

## Per degradation model

| degradation model | calls | s/call | total s |
| --- | ---: | ---: | ---: |
| paper_overlay | 33 | 0.3688 | 12.170 |
| bleed_through | 6 | 0.2553 | 1.532 |
| blur_zones | 54 | 0.1240 | 6.698 |
| ink_degradation | 75 | 0.1236 | 9.271 |
| paper_texture | 84 | 0.1194 | 10.027 |
| gradient_domain | 15 | 0.1101 | 1.652 |
| shadow_binding | 30 | 0.0240 | 0.721 |
| phantom_character | 18 | 0.0142 | 0.256 |
| holes | 30 | 0.0040 | 0.121 |
| blur | 6 | 0.0018 | 0.011 |

## What the declared run costs

`pipeline.yaml` as it stands, priced with the model above. The worker starts **one renderer process per shard**. It used to start one per *run*, and a run is one layout, so a twenty-image shard over fourteen layouts started fourteen processes drawing one and a half images each and paid start-up fourteen times.

| backend | images | processes | s | was (1 per layout) | saved |
| --- | ---: | ---: | ---: | ---: | ---: |
| genalog | 20 | 1 (was 14) | 17.1 | 29.2 | 42% |
| html | 20 | 1 (was 14) | 26.3 | 37.5 | 30% |
| synthdog | 20 | 1 (was 14) | 50.5 | 66.0 | 23% |

That was the largest lever this profile found, and it was not in a renderer or in a degradation model: it was the shape of the invocation. The renderers take a job list now (`worklist.py`), and the same plan went from 140 s to 98 s measured end to end. The saving predicted from this model before the change was made came within 7.3% of the saving measured after it -- which is the first time the cost model was used rather than merely built.

## What this names, and what it clears

* `gradient_domain`: 0.110 s a call, 1.7 s over 15 calls -- 4% of all the ageing measured here.
* `paper_overlay`: 0.369 s a call, 12.2 s over 33 calls -- 29% of all the ageing measured here.
* Dearest ageing model overall: `paper_overlay`, 29% of the ageing time.
* Dearest stage of `synthdog`: `scene`, 49% of its wall clock.
* Dearest stage of `html`: `render`, 46% of its wall clock.
* Dearest stage of `genalog`: `degradation`, 54% of its wall clock.

Read that list before optimising anything. The stage a profile clears is worth as much as the one it names: an afternoon spent on a model that is a few percent of the ageing buys a few percent of a fraction, and the reason to measure first is that this cannot be told by reading the code.

## What the measurement cost

The stopwatch was entered 1625 times at 507 ns a time -- 0.0008 s, 0.0005% of the run. A profile whose instrument costs a noticeable share of what it measures is a measurement of the instrument.

## The cost model

The model was checked against a run it was not fitted on: `html` x5 at seed 140000 was predicted at 7.23 s and took 6.44 s -- the model predicted **high** by 12.2%. The direction matters when the model is used to size a run: high is the safe side, and saying which side it errs on is part of the number. A different seed draws a different mix of layouts and ageing, which is the situation the model is for and the one where it can be wrong.

`cost_model.json` beside this file holds the same numbers as seconds per image per stage, seconds per call per degradation model, and the fixed cost of starting each backend. `predict()` in `tools/profile_pipeline.py` turns a plan into an expected duration from it. The point of keeping it machine-readable is that a later load test can predict before it runs and compare afterwards: where prediction and clock disagree, that gap is the finding.

