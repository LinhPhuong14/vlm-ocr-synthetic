# Where the time goes

Measured by `tools/profile_pipeline.py`. Every stage is timed, including the ones nobody suspects; the interpreter start-up a child process cannot see is measured from outside and named, so the column adds up to the wall clock rather than to most of it.

## Per stage, per renderer

| stage | genalog s | genalog % | html s | html % | synthdog s | synthdog % |
| --- | ---: | ---: | ---: | ---: | ---: | ---: |
| interpreter | 0.899 | 12.4% | 0.238 | 2.1% | 1.257 | 5.1% |
| startup | 0.000 | 0.0% | 0.505 | 4.5% | 0.006 | 0.0% |
| sampling | 0.620 | 8.5% | 0.574 | 5.2% | 0.602 | 2.4% |
| content | 0.004 | 0.0% | 0.004 | 0.0% | 0.004 | 0.0% |
| layout | 0.039 | 0.5% | 0.038 | 0.3% | 0.040 | 0.2% |
| render | 1.677 | 23.1% | 4.894 | 44.0% | 5.037 | 20.5% |
| geometry | 0.005 | 0.1% | 0.229 | 2.1% | 13.560 | 55.1% |
| degradation | 3.928 | 54.2% | 4.576 | 41.1% | 3.995 | 16.2% |
| annotation | 0.002 | 0.0% | 0.002 | 0.0% | 0.003 | 0.0% |
| validation | 0.002 | 0.0% | 0.002 | 0.0% | 0.002 | 0.0% |
| export | 0.067 | 0.9% | 0.068 | 0.6% | 0.083 | 0.3% |
| *unattributed* | 0.005 | 0.1% | 0.002 | 0.0% | 0.020 | 0.1% |

`interpreter` and `startup` are paid once per process, not per image, so their share shrinks as a run gets longer; every other row scales with the image count.

## Per degradation model

| degradation model | calls | s/call | total s |
| --- | ---: | ---: | ---: |
| paper_overlay | 33 | 0.3355 | 11.072 |
| bleed_through | 6 | 0.1396 | 0.838 |
| blur_zones | 54 | 0.1223 | 6.605 |
| ink_degradation | 75 | 0.1168 | 8.759 |
| paper_texture | 84 | 0.1128 | 9.473 |
| gradient_domain | 15 | 0.1102 | 1.654 |
| shadow_binding | 30 | 0.0213 | 0.639 |
| phantom_character | 18 | 0.0137 | 0.247 |
| holes | 30 | 0.0037 | 0.112 |
| blur | 6 | 0.0015 | 0.009 |

## What the declared run costs

`pipeline.yaml` as it stands, priced with the model above. The worker starts one renderer process per *run*, and a run is one layout, so a twenty-image shard over fourteen layouts starts fourteen processes that draw about one and a half images each -- and the fixed cost is paid fourteen times.

| backend | processes | images | images/process | predicted s | of which start-up | share |
| --- | ---: | ---: | ---: | ---: | ---: | ---: |
| genalog | 14 | 20 | 1.43 | 28.5 | 12.6 | 44% |
| html | 14 | 20 | 1.43 | 36.4 | 10.4 | 29% |
| synthdog | 14 | 20 | 1.43 | 76.0 | 17.7 | 23% |

That column is the largest lever this profile found, and it is not in a renderer or in a degradation model: it is the shape of the plan. Handing a renderer all of a shard's layouts in one invocation would pay the start-up once instead of once per layout. Doing it is a change to the worker and to all three renderers' arguments, so it is measured here and left named rather than done as part of a measurement.

## What this names, and what it clears

* `gradient_domain`: 0.110 s a call, 1.7 s over 15 calls -- 4% of all the ageing measured here.
* `paper_overlay`: 0.336 s a call, 11.1 s over 33 calls -- 28% of all the ageing measured here.
* Dearest ageing model overall: `paper_overlay`, 28% of the ageing time.
* Dearest stage of `genalog`: `degradation`, 54% of its wall clock.
* Dearest stage of `html`: `render`, 44% of its wall clock.
* Dearest stage of `synthdog`: `geometry`, 55% of its wall clock.

Read that list before optimising anything. The stage a profile clears is worth as much as the one it names: an afternoon spent on a model that is a few percent of the ageing buys a few percent of a fraction, and the reason to measure first is that this cannot be told by reading the code.

## What the measurement cost

The stopwatch was entered 1541 times at 503 ns a time -- 0.0008 s, 0.0005% of the run. A profile whose instrument costs a noticeable share of what it measures is a measurement of the instrument.

## The cost model

The model was checked against a run it was not fitted on: `html` x5 at seed 140000 was predicted at 7.24 s and took 6.77 s, an error of -7.0%. A different seed draws a different mix of layouts and ageing, which is the situation the model is for and the one where it can be wrong.

`cost_model.json` beside this file holds the same numbers as seconds per image per stage, seconds per call per degradation model, and the fixed cost of starting each backend. `predict()` in `tools/profile_pipeline.py` turns a plan into an expected duration from it. The point of keeping it machine-readable is that a later load test can predict before it runs and compare afterwards: where prediction and clock disagree, that gap is the finding.

