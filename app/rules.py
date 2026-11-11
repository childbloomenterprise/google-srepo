import re
from functools import lru_cache
from pathlib import Path

RULES_PATH = Path(__file__).with_name("rules.md")
RULE_ID_PATTERN = re.compile(r"^(R\d\d) ", re.MULTILINE)


@lru_cache(maxsize=1)
def load_rulebook() -> str:
    return RULES_PATH.read_text(encoding="utf-8")


@lru_cache(maxsize=1)
def rule_ids() -> set[str]:
    return set(RULE_ID_PATTERN.findall(load_rulebook()))
