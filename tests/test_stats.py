import pytest
import numpy as np
import pandas as pd
from src.analysis.stats_analyzer import StatisticalAnalyzer
from src.analysis.layer_validation import LayerValidation

def test_firth_logistic_separation():
    """
    Test that Firth's penalized logistic regression successfully converges
    and provides stable estimates (and Wald CIs) on a dataset with complete separation,
    whereas standard MLE logistic regression fails or yields absurdly large standard errors.
    """
    # Create a dataset with complete separation:
    # y is 1 if x > 0 else 0
    np.random.seed(42)
    x = np.array([-3.0, -2.0, -1.0, 1.0, 2.0, 3.0])
    y = np.array([0, 0, 0, 1, 1, 1])
    
    # Design matrix with intercept
    X = np.column_stack((np.ones_like(x), x))
    
    # We instantiate StatisticalAnalyzer with a dummy dataframe
    dummy_df = pd.DataFrame({
        "subject": ["agent"] * 6,
        "cnlv": x,
        "task_failed": y,
        "repo_id": ["repo1"] * 6,
        "repo_size": ["small"] * 6,
        "repo_domain": ["web"] * 6
    })
    
    analyzer = StatisticalAnalyzer(dummy_df)
    
    # 1. Run separation diagnostic directly
    import statsmodels.api as sm
    logit_mod = sm.Logit(y, X).fit(disp=False)
    # Standard MLE standard errors should blow up (large values)
    assert np.any(logit_mod.bse > 10.0)
    
    # 2. Fit Firth
    beta, se, p_values = analyzer.fit_firth_logistic(X, y)
    
    # Firth coefficient for x (beta[1]) should be finite and reasonable (usually around 1.5 - 3.0 for this size)
    assert np.isfinite(beta[1])
    assert np.isfinite(se[1])
    assert se[1] < 10.0  # Firth standard error should be small/reasonable
    assert beta[1] > 0.0  # Positive relationship
    
    # 3. Test run_downstream_risk_analysis integration
    risk_results = analyzer.run_downstream_risk_analysis()
    assert risk_results["separation_detected"] is True
    assert risk_results["model_type"] == "Firth Penalized Logistic"
    assert risk_results["or_upper_95"] > risk_results["odds_ratio"]
    assert risk_results["or_lower_95"] < risk_results["odds_ratio"]


def test_domain_stratified_multiple_comparisons():
    """
    Verify multiple comparisons corrections (Bonferroni and BH-FDR) on domain-stratified tests.
    """
    # Construct synthetic data where some domains have significant differences and others do not
    np.random.seed(42)
    data = []
    # Domain 1 (web): Agent has much higher drift than Human
    data.extend([{"subject": "agent", "repo_domain": "web", "cnlv": np.random.normal(0.8, 0.1)} for _ in range(10)])
    data.extend([{"subject": "human", "repo_domain": "web", "cnlv": np.random.normal(0.0, 0.05)} for _ in range(10)])
    
    # Domain 2 (cli): Agent has slightly higher drift
    data.extend([{"subject": "agent", "repo_domain": "cli", "cnlv": np.random.normal(0.4, 0.1)} for _ in range(10)])
    data.extend([{"subject": "human", "repo_domain": "cli", "cnlv": np.random.normal(0.3, 0.1)} for _ in range(10)])
    
    # Domain 3 (library): No difference
    data.extend([{"subject": "agent", "repo_domain": "library", "cnlv": np.random.normal(0.1, 0.1)} for _ in range(10)])
    data.extend([{"subject": "human", "repo_domain": "library", "cnlv": np.random.normal(0.1, 0.1)} for _ in range(10)])
    
    df = pd.DataFrame(data)
    # Ensure columns expected by grouped analyses exist
    df["repo_id"] = "dummy"
    
    analyzer = StatisticalAnalyzer(df)
    strat_df = analyzer.run_domain_stratified_tests(metric="cnlv")
    
    assert len(strat_df) == 3
    assert "p_raw" in strat_df.columns
    assert "p_bonferroni" in strat_df.columns
    assert "p_bh" in strat_df.columns
    
    # Bonferroni should be exactly raw_p * 3 (capped at 1.0)
    for _, row in strat_df.iterrows():
        assert np.isclose(row["p_bonferroni"], min(row["p_raw"] * 3, 1.0))
        # FDR adjusted p-value should be >= raw p-value
        assert row["p_bh"] >= row["p_raw"]


def test_cohens_kappa_calculation():
    """
    Test percent agreement and Cohen's kappa calculations.
    """
    # 1. Perfect agreement
    df_perfect = pd.DataFrame({
        "heuristic": ["L1", "L2", "L3", "L4"],
        "second_rater": ["L1", "L2", "L3", "L4"]
    })
    p_o, kappa = LayerValidation.calculate_agreement(df_perfect)
    assert p_o == 1.0
    assert kappa == 1.0
    
    # 2. Specific case with some disagreements
    df_disagree = pd.DataFrame({
        "heuristic":    ["L1", "L1", "L2", "L2", "L3", "L3", "L4", "L4"],
        "second_rater": ["L1", "L2", "L2", "L2", "L3", "L3", "L4", "L1"]
    })
    # 6 agreements out of 8 = 75% observed agreement
    p_o, kappa = LayerValidation.calculate_agreement(df_disagree)
    assert p_o == 0.75
    assert kappa < 1.0
