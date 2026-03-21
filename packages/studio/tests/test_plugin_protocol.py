from forge_studio.plugin_protocol import RoundResult


def test_round_result_to_dict():
    r = RoundResult(
        round_number=1,
        status="keep",
        total_before=70,
        total_after=74,
        delta=4,
        target_dimension="对白质量",
        description="Improved dialogue",
        scores_before={"结构": 18, "对白": 14},
        scores_after={"结构": 18, "对白": 18},
        max_total=100,
    )
    d = r.to_dict()
    assert d["round_number"] == 1
    assert d["status"] == "keep"
    assert d["scores_before"]["对白"] == 14
    assert d["scores_after"]["对白"] == 18


def test_round_result_from_experiment_record():
    """RoundResult.from_experiment_record should convert correctly."""
    from unittest.mock import MagicMock

    record = MagicMock()
    record.id = 1
    record.sequence = "seq_01"
    record.mode = "micro"
    record.target_dimension = "对白"
    record.hypothesis = "test"
    record.scope = "scene"
    record.description = "Modified dialogue"
    record.delta = 4
    record.status = "keep"
    record.score_before.total = 70
    record.score_after.total = 74
    record.score_before.scores = {"结构": 18, "对白": 14}
    record.score_after.scores = {"结构": 18, "对白": 18}
    record.score_before.max_total = 100
    record.score_after.max_total = 100

    r = RoundResult.from_experiment_record(record, round_number=3)
    assert r.round_number == 3
    assert r.total_before == 70
    assert r.total_after == 74
    assert r.max_total == 100
