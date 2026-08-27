import pytest
import numpy as np
from src.metrics.evaluator import MetricsEvaluator

def test_compute_dged():
    """Verify Dependency Graph Edit Distance calculation."""
    v_pre = {"domain", "service", "api"}
    e_pre = {("service", "domain"), ("api", "service")}

    v_post = {"domain", "service", "api", "utils"}
    e_post = {("service", "domain"), ("api", "service"), ("domain", "utils"), ("api", "utils")}

    # Difference: 1 new node ('utils'), 2 new edges (domain->utils, api->utils)
    dged = MetricsEvaluator.compute_dged(v_pre, e_pre, v_post, e_post)
    assert dged == 3


def test_compute_lvc():
    """Verify Layering Violation Count against explicit forbidden layer rules."""
    layers = {
        "L1_domain": ["domain"],
        "L2_service": ["service"],
        "L3_adapter": ["adapters"]
    }
    forbidden_rules = [
        {"source": "L1_domain", "target": ["L2_service", "L3_adapter"]}
    ]

    e_pre = {("service", "domain")}
    # Edge added: domain -> adapters (ILLEGAL: L1_domain -> L3_adapter)
    e_post = {("service", "domain"), ("domain", "adapters")}

    lvc_count, violations = MetricsEvaluator.compute_lvc(e_pre, e_post, layers, forbidden_rules)
    assert lvc_count == 1
    assert len(violations) == 1
    assert violations[0][0] == "domain"
    assert violations[0][1] == "adapters"


def test_compute_normalized_lvc():
    """Verify Normalized LVC calculation per 1000 baseline edges."""
    lvc = 2
    baseline_edges = 3
    # LVC_norm = (2 / (3 + 1)) * 1000 = 500.0
    lvc_norm = MetricsEvaluator.compute_normalized_lvc(lvc, baseline_edges)
    assert lvc_norm == 500.0


def test_compute_cdr():
    """Verify Conformance Decay Rate linear regression slope beta_CDR."""
    lvc_series = [0.0, 1.0, 2.0, 3.0]
    beta_cdr = MetricsEvaluator.compute_cdr(lvc_series)
    assert np.isclose(beta_cdr, 1.0)


def test_compute_cnlv():
    """Verify Complexity-Normalized Layering Violation."""
    lvc = 2
    cc_pre = 20
    cc_post = 30  # delta CC = 10
    cnlv = MetricsEvaluator.compute_cnlv(lvc, cc_pre, cc_post)
    assert cnlv == 0.20
