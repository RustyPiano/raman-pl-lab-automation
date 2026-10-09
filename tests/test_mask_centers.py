import pytest

from lab_auto.vision.mask_centers import SampleCenter, extract_centers


def test_single_rectangular_blob_returns_one_centroid():
    # 0 0 0 0
    # 0 1 1 0
    # 0 1 1 0
    # 0 0 0 0
    mask = [
        [0, 0, 0, 0],
        [0, 1, 1, 0],
        [0, 1, 1, 0],
        [0, 0, 0, 0],
    ]
    centers = extract_centers(mask)
    assert len(centers) == 1
    c = centers[0]
    assert isinstance(c, SampleCenter)
    assert c.pixel_x == pytest.approx(1.5)
    assert c.pixel_y == pytest.approx(1.5)
    assert c.area == 4


def test_two_separated_blobs_return_two_centers():
    mask = [
        [1, 1, 0, 0, 0],
        [1, 1, 0, 0, 0],
        [0, 0, 0, 0, 0],
        [0, 0, 0, 1, 1],
        [0, 0, 0, 1, 1],
    ]
    centers = extract_centers(mask)
    assert len(centers) == 2
    # deterministic ordering by (round(y), round(x)): top-left blob first
    assert centers[0].pixel_x == pytest.approx(0.5)
    assert centers[0].pixel_y == pytest.approx(0.5)
    assert centers[1].pixel_x == pytest.approx(3.5)
    assert centers[1].pixel_y == pytest.approx(3.5)


def test_diagonal_touch_stays_separate_with_4_connectivity():
    mask = [
        [1, 0],
        [0, 1],
    ]
    centers = extract_centers(mask)
    assert len(centers) == 2


def test_min_area_filters_noise():
    mask = [
        [1, 1, 0, 0],
        [1, 1, 0, 0],
        [0, 0, 0, 1],
        [0, 0, 0, 0],
    ]
    # the lone pixel (area 1) is filtered when min_area=2
    centers = extract_centers(mask, min_area=2)
    assert len(centers) == 1
    assert centers[0].area == 4


def test_nonzero_labels_are_foreground():
    # any nonzero value counts as foreground; one connected region
    mask = [
        [0, 7, 7],
        [0, 3, 0],
    ]
    centers = extract_centers(mask)
    assert len(centers) == 1
    assert centers[0].area == 3


def test_empty_and_all_zero_mask_return_empty():
    assert extract_centers([]) == []
    assert extract_centers([[0, 0], [0, 0]]) == []


def test_labels_are_unique_and_stable():
    mask = [
        [1, 1, 0, 0, 0],
        [1, 1, 0, 0, 0],
        [0, 0, 0, 1, 1],
        [0, 0, 0, 1, 1],
    ]
    centers = extract_centers(mask)
    labels = [c.label for c in centers]
    assert len(set(labels)) == len(labels)
