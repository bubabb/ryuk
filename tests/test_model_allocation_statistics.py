import pytest

from scripts.model_allocation_statistics import (
    newcombe_paired_interval,
    paired_noninferiority,
)


@pytest.mark.parametrize(
    "cells,expected",
    [
        ((36, 12, 2, 0), (0.0569, 0.3404)),
        ((35, 14, 0, 1), (0.1461, 0.4175)),
        ((18, 14, 0, 18), (0.1441, 0.3963)),
        ((1, 97, 1, 1), (0.8736, 0.9850)),
        ((0, 30, 0, 0), (0.8395, 1.0)),
        ((54, 0, 0, 0), (-0.0664, 0.0664)),
    ],
)
def test_newcombe_method_10_matches_published_table_iii(cells, expected):
    interval = newcombe_paired_interval(*cells)
    # The paper prints four decimals, with one entry apparently truncated.
    assert interval.lower == pytest.approx(expected[0], abs=0.0001)
    assert interval.upper == pytest.approx(expected[1], abs=0.0001)


def test_orientation_and_noninferiority_boundary_are_explicit():
    interval = newcombe_paired_interval(90, 5, 3, 2)
    assert interval.difference == pytest.approx(0.02)
    assert not paired_noninferiority(interval, margin=0.03)["passed"]
    threshold_interval = interval.__class__(
        **{**interval.as_dict(), "lower": -0.03}
    )
    assert not paired_noninferiority(threshold_interval, margin=0.03)["passed"]


@pytest.mark.parametrize(
    "cells,confidence",
    [
        ((-1, 0, 0, 0), 0.95),
        ((True, 0, 0, 0), 0.95),
        ((0, 0, 0, 0), 0.95),
        ((1, 0, 0, 0), 1),
        ((1, 0, 0, 0), 1.0),
    ],
)
def test_invalid_inputs_fail_closed(cells, confidence):
    with pytest.raises(ValueError):
        newcombe_paired_interval(*cells, confidence_level=confidence)


@pytest.mark.parametrize("margin", [-0.01, 1.0, 0, True])
def test_invalid_noninferiority_margin_fails_closed(margin):
    interval = newcombe_paired_interval(1, 0, 0, 0)
    with pytest.raises(ValueError):
        paired_noninferiority(interval, margin=margin)
