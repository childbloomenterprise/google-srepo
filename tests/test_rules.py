from app.rules import load_rulebook, rule_ids


def test_rules_parser_finds_all_fifteen_ids():
    assert rule_ids() == {f"R{number:02d}" for number in range(1, 16)}
    assert load_rulebook().startswith("# ClaimBack rulebook")
