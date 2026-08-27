"""
tests/test_matched_baseline.py
Unit tests for the matched-task baseline extraction logic.

These tests exercise the three matching criteria in isolation using
hand-constructed commit-like data, so no git repo is required.
"""
import pytest
from src.human_baseline.baseline_extractor import (
    _classify_intent,
    _subsystem_of_file,
    _files_subsystems,
    SUBSYSTEM_OVERLAP_MIN,
    FILE_TOUCH_TOLERANCE,
)

# ---------------------------------------------------------------------------
# Test corpus: canonical layer map used by all tests
# ---------------------------------------------------------------------------
LAYERS = {
    "L1_domain":     ["src/domain/", "src/models/"],
    "L2_service":    ["src/services/", "src/manager/"],
    "L3_adapter":    ["src/adapters/", "src/db/"],
    "L4_entrypoint": ["src/api/", "src/cli/"],
}


# ---------------------------------------------------------------------------
# 1. Intent classification
# ---------------------------------------------------------------------------
class TestIntentClassification:

    def test_bugfix_keywords(self):
        assert _classify_intent("Fix regression in auth flow") == "bugfix"
        assert _classify_intent("patch: null pointer in user model") == "bugfix"

    def test_feature_keywords(self):
        assert _classify_intent("Add OAuth2 provider support") == "feature"
        assert _classify_intent("Implement rate limiting middleware") == "feature"

    def test_refactor_keywords(self):
        assert _classify_intent("Refactor database adapter layer") == "refactor"
        assert _classify_intent("Rename UserService to AccountService") == "refactor"

    def test_unknown_when_no_keyword_matches(self):
        assert _classify_intent("Update changelog and version bump") == "unknown"
        assert _classify_intent("Bump dependency version to 2.1.0") == "unknown"

    def test_case_insensitive(self):
        assert _classify_intent("FIX: broken import path") == "bugfix"
        assert _classify_intent("ADD new CLI subcommand") == "feature"


# ---------------------------------------------------------------------------
# 2. Subsystem assignment
# ---------------------------------------------------------------------------
class TestSubsystemAssignment:

    def test_exact_prefix_match(self):
        assert _subsystem_of_file("src/domain/entities.py", LAYERS) == "L1_domain"
        assert _subsystem_of_file("src/api/router.py", LAYERS) == "L4_entrypoint"
        assert _subsystem_of_file("src/db/session.py", LAYERS) == "L3_adapter"

    def test_no_match_returns_none(self):
        assert _subsystem_of_file("tests/test_core.py", LAYERS) is None
        assert _subsystem_of_file("setup.py", LAYERS) is None

    def test_trailing_slash_tolerance(self):
        # Prefix defined with trailing slash should still match file inside
        assert _subsystem_of_file("src/domain/user.py", LAYERS) == "L1_domain"


# ---------------------------------------------------------------------------
# 3. Scope-equivalency gate
# ---------------------------------------------------------------------------
class TestScopeEquivalency:
    """
    FILE_TOUCH_TOLERANCE is 2.  A commit that touches agent_count ± 2 files
    should pass; anything further should be rejected.
    """

    def test_within_tolerance_passes(self):
        agent_count = 5
        for human_count in [3, 4, 5, 6, 7]:
            assert abs(human_count - agent_count) <= FILE_TOUCH_TOLERANCE, (
                f"human_count={human_count} should be within tolerance"
            )

    def test_outside_tolerance_fails(self):
        agent_count = 5
        for human_count in [1, 2, 8, 9]:
            assert abs(human_count - agent_count) > FILE_TOUCH_TOLERANCE, (
                f"human_count={human_count} should be outside tolerance"
            )


# ---------------------------------------------------------------------------
# 4. Subsystem-locality gate
# ---------------------------------------------------------------------------
class TestSubsystemLocality:
    """
    Verifies that the overlap computation correctly accepts/rejects commits
    based on the SUBSYSTEM_OVERLAP_MIN threshold.
    """

    def _overlap_ratio(self, agent_files, human_files):
        agent_layers = _files_subsystems(agent_files, LAYERS)
        human_layers = _files_subsystems(human_files, LAYERS)
        shared = set(agent_layers.keys()) & set(human_layers.keys()) - {"unknown"}
        all_l  = set(agent_layers.keys()) | set(human_layers.keys()) - {"unknown"}
        return len(shared) / len(all_l) if all_l else 0.0

    def test_same_layer_gives_full_overlap(self):
        agent = ["src/domain/entities.py", "src/domain/user.py"]
        human = ["src/domain/order.py",    "src/domain/product.py"]
        ratio = self._overlap_ratio(agent, human)
        assert ratio >= SUBSYSTEM_OVERLAP_MIN

    def test_disjoint_layers_below_threshold(self):
        agent = ["src/domain/entities.py"]           # L1_domain
        human = ["src/api/router.py"]                # L4_entrypoint
        ratio = self._overlap_ratio(agent, human)
        assert ratio < SUBSYSTEM_OVERLAP_MIN

    def test_partial_overlap_at_threshold(self):
        # Agent touches L1 + L2; Human touches L2 + L3
        # shared = {L2}, all = {L1, L2, L3} => 1/3 ≈ 0.33 >= 0.30
        agent = ["src/domain/entities.py", "src/services/auth.py"]
        human = ["src/services/token.py",  "src/adapters/postgres.py"]
        ratio = self._overlap_ratio(agent, human)
        assert ratio >= SUBSYSTEM_OVERLAP_MIN
