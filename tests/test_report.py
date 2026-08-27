"""The run's verdict, and the bar that shows it being reached.

Three files, one contract each:

* `pipeline/imagetimes.py` -- one line per image, readable after a kill.
* `pipeline/report.py`     -- every shard is a case, and `resumed` is not
  `pass`: a run must not take credit for an earlier run's work.
* `pipeline/progress.py`   -- stderr and a terminal, or plain lines. A bar on
  stdout would be inside the JSON that `pipeline/worker.py` answers with.
"""

from __future__ import annotations

import io
import json

import pytest

from pipeline import imagetimes, progress, report

PLAN = {
    "shards": [
        {"index": 0, "backend": "html", "count": 2,
         "runs": [{"layout": "market_vat", "seed": 1, "count": 2, "first_index": 0}]},
        {"index": 1, "backend": "html", "count": 2,
         "runs": [{"layout": "eatery_ascii", "seed": 3, "count": 2, "first_index": 2}]},
    ],
}

FRAMEWORKS = {"html": {"images": 4}}


def verdict(results, *, checks=(), warnings=(), done=None, times=()):
    return report.build(
        plan=PLAN, results=list(results), frameworks=FRAMEWORKS,
        warnings=list(warnings), checks=list(checks), elapsed=12.0, workers=2,
        times=list(times),
        done=done if done is not None else {0: True, 1: True})


# --------------------------------------------------------------- imagetimes


def test_a_time_survives_the_image_that_raised(tmp_path):
    """The row is written in a `finally`, and that is the point of it.

    A page that dies slowly is exactly the page somebody is timing, so the
    entry must be on disk before the exception leaves the block.
    """
    with imagetimes.Log(tmp_path) as clock:
        with pytest.raises(ValueError):
            with clock.time("html_000.jpg", layout="market_vat"):
                raise ValueError("the renderer fell over")

    entries = imagetimes.read(tmp_path)
    assert list(entries) == ["html_000.jpg"]
    assert entries["html_000.jpg"].layout == "market_vat"


def test_a_torn_last_line_does_not_lose_the_rest(tmp_path):
    """A killed process leaves half a line. Nine good rows are still nine."""
    path = imagetimes.beside(tmp_path)
    path.write_text(
        json.dumps({"file": "a.jpg", "layout": "market_vat", "seconds": 1.0}) + "\n"
        + '{"file": "b.jpg", "sec',
        encoding="utf-8")
    assert list(imagetimes.read(tmp_path)) == ["a.jpg"]


def test_the_summary_says_where_the_time_went():
    entries = [imagetimes.Entry(file=f"html_{i:03d}.jpg",
                                layout="market_vat" if i < 3 else "eatery_ascii",
                                seconds=float(i + 1), stages={"draw": float(i)})
               for i in range(4)]
    summary = imagetimes.summarise(entries)

    assert summary["images"] == 4
    assert summary["seconds_total"] == 10.0
    assert summary["slowest"]["file"] == "html_003.jpg"
    assert summary["by_layout"]["market_vat"]["images"] == 3
    assert summary["seconds_by_stage"]["draw"] == 6.0
    # No images at all is a fact, not an error: a run with the timing switched
    # off still has to be able to write its report.
    assert imagetimes.summarise([]) == {"images": 0}


# ------------------------------------------------------------------- report


def test_a_run_where_everything_worked_passes():
    payload = verdict([
        {"shard": 0, "backend": "html", "images": 2, "skipped": False,
         "error": None, "seconds": 6.0},
        {"shard": 1, "backend": "html", "images": 2, "skipped": False,
         "error": None, "seconds": 6.0},
    ], checks=[{"name": "drift", "status": report.PASS, "detail": ""}])

    assert payload["verdict"] == report.PASS
    assert payload["cases"] == {"shards": 2, "passed": 2, "resumed": 0,
                                "failed": 0, "checks": 1, "checks_failed": 0}


def test_a_resumed_shard_is_not_counted_as_a_pass():
    """This run drew nothing. Saying it passed two shards would be a lie."""
    payload = verdict([])

    assert payload["cases"]["passed"] == 0
    assert payload["cases"]["resumed"] == 2
    assert payload["verdict"] == report.PASS
    assert [case["status"] for case in payload["shards"]] == ["resumed", "resumed"]


def test_a_shard_that_never_ran_and_never_finished_is_a_failure():
    """Not in the results and no DONE: it is missing, not merely untouched."""
    payload = verdict([], done={0: True, 1: False})

    assert payload["verdict"] == report.FAIL
    assert payload["shards"][1]["status"] == report.FAIL
    assert payload["shards"][1]["images"] == 0


def test_one_failed_check_fails_the_run_with_every_shard_intact():
    payload = verdict(
        [{"shard": 0, "backend": "html", "images": 2, "skipped": False,
          "error": None, "seconds": 6.0},
         {"shard": 1, "backend": "html", "images": 2, "skipped": False,
          "error": None, "seconds": 6.0}],
        checks=[{"name": "drift", "status": report.FAIL, "detail": "mix lệch"}])

    assert payload["cases"]["failed"] == 0
    assert payload["verdict"] == report.FAIL


def test_a_failed_shard_keeps_only_the_first_line_of_its_error():
    payload = verdict([
        {"shard": 0, "backend": "html", "images": 0, "skipped": False,
         "seconds": 1.0, "error": "shard 0 html failed (exit 1):\nTraceback…\n  more"},
        {"shard": 1, "backend": "html", "images": 2, "skipped": False,
         "error": None, "seconds": 6.0},
    ])

    assert payload["verdict"] == report.FAIL
    assert payload["shards"][0]["error"] == "shard 0 html failed (exit 1):"


def test_the_console_summary_names_every_failure():
    payload = verdict(
        [{"shard": 0, "backend": "html", "images": 0, "skipped": False,
          "seconds": 1.0, "error": "shard 0 html failed (exit 1)"},
         {"shard": 1, "backend": "html", "images": 2, "skipped": False,
          "error": None, "seconds": 6.0}],
        checks=[{"name": "drift", "status": report.FAIL, "detail": "mix lệch"}],
        warnings=["html: 4 images but only 3 distinct labels"],
        times=[imagetimes.Entry(file="html_000.jpg", layout="market_vat",
                                seconds=2.0)])
    text = report.render(payload)

    assert text.startswith("KẾT QUẢ: FAIL")
    assert "shard 0" in text and "mix lệch" in text
    assert "distinct labels" in text
    assert "market_vat" in text


# ----------------------------------------------------------------- progress


def test_the_bar_never_writes_to_stdout(capsys):
    """Everything downstream reads stdout. The bar is a view, not a record."""
    bar = progress.Bar(10, stream=io.StringIO(), enabled=True)
    bar.advance(5, note="market_vat")
    bar.close()
    assert capsys.readouterr().out == ""


def test_the_bar_shows_the_count_the_share_and_what_is_being_drawn():
    bar = progress.Bar(200, stream=io.StringIO(), enabled=True)
    bar.set(50, note="market_vat")
    line = bar.render(width=100)

    assert "50/200 ảnh" in line and "25%" in line and "market_vat" in line
    assert line.startswith("[" + progress.FULL)
    assert progress.EMPTY in line


def test_without_a_terminal_it_prints_plain_lines_and_no_carriage_return():
    """A carriage return in a CI log turns a run into one enormous line."""
    stream = io.StringIO()
    bar = progress.Bar(100, stream=stream, enabled=False)
    for _ in range(100):
        bar.advance(1)
    bar.close()
    written = stream.getvalue()

    assert "\r" not in written
    assert written.count("\n") == 100 // progress.QUIET_EVERY
    assert "100/100 ảnh (100%" in written


def test_a_message_printed_mid_run_is_not_eaten_by_the_bar():
    stream = io.StringIO()
    bar = progress.Bar(10, stream=stream, enabled=True)
    bar.advance(1)
    bar.say("  [FAILED] shard 3")
    bar.close()

    assert "[FAILED] shard 3\n" in stream.getvalue()


def test_a_duration_is_never_more_precise_than_it_deserves():
    assert progress.duration(9) == "9s"
    assert progress.duration(252) == "4m12s"
    assert progress.duration(3780) == "1h03m"
