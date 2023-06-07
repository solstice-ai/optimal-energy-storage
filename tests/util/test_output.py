from oes.util.output import pretty_time


def test_pretty_time():
    assert pretty_time(0) == "0s"
    assert pretty_time(1) == "1s"
    assert pretty_time(59) == "59s"
    assert pretty_time(60) == "1m 0s"
    assert pretty_time(61) == "1m 1s"
    assert pretty_time(119) == "1m 59s"
    assert pretty_time(120) == "2m 0s"
    assert pretty_time((60 * 50) + 12) == "50m 12s"
    assert pretty_time((60 * 60) + 12) == "1h 0m 12s"
    assert pretty_time((60 * 60 * 2) + (60 * 50) + 12) == "2h 50m 12s"
