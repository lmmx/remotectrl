import pytest

from remotectrl.policy import ok


@pytest.mark.parametrize(
    ("ahead", "behind", "mine", "expected"),
    [
        # mine=True: only `behind` matters (design doc §5 mirror own-branch / backup own-branch)
        (0, 0, True, True),
        (5, 0, True, True),  # ahead is normal for mine=True
        (0, 1, True, False),  # any behind blocks
        (5, 1, True, False),
        (0, 100, True, False),
        # mine=False: only `ahead` matters (design doc §5 mirror other-branches)
        (0, 0, False, True),
        (0, 5, False, True),  # behind is normal for mine=False
        (1, 0, False, False),  # any ahead blocks
        (1, 5, False, False),
        (100, 0, False, False),
    ],
)
def test_ok_truth_table(ahead: int, behind: int, mine: bool, expected: bool) -> None:
    assert ok(ahead, behind, mine) is expected
