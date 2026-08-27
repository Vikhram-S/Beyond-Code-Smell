import numpy as np
import pandas as pd
from scipy import stats
import statsmodels.api as sm
import statsmodels.formula.api as smf
from typing import Dict, Any, Tuple

class StatisticalAnalyzer:
    """
    Statistical analysis engine for Architectural Conformance Drift.
    Performs assumption diagnostics, descriptive stats (median/IQR),
    non-parametric Mann-Whitney U testing with effect sizes,
    Linear Mixed-Effects Models (LMM), power analysis, and risk correlation.
    """

    def __init__(self, df: pd.DataFrame):
        self.df = df.copy()

    def check_assumptions(self, metric: str = "cnlv") -> Dict[str, Any]:
        """
        Evaluates distributional assumptions (Shapiro-Wilk test for normality,
        Levene's test for homoscedasticity) and logs conclusions.
        """
        agent_vals = self.df[self.df["subject"] == "agent"][metric].dropna()
        human_vals = self.df[self.df["subject"] == "human"][metric].dropna()

        # Shapiro-Wilk Test for Normality
        stat_agent, p_agent = stats.shapiro(agent_vals) if len(agent_vals) >= 3 else (0.0, 1.0)
        stat_human, p_human = stats.shapiro(human_vals) if len(human_vals) >= 3 else (0.0, 1.0)

        # Levene's Test for Equality of Variances
        stat_lev, p_lev = stats.levene(agent_vals, human_vals)

        is_normal = (p_agent > 0.05) and (p_human > 0.05)

        diagnostics = {
            "metric": metric,
            "shapiro_agent_stat": float(stat_agent),
            "shapiro_agent_p": float(p_agent),
            "agent_is_normal": bool(p_agent > 0.05),
            "shapiro_human_stat": float(stat_human),
            "shapiro_human_p": float(p_human),
            "human_is_normal": bool(p_human > 0.05),
            "levene_stat": float(stat_lev),
            "levene_p": float(p_lev),
            "equal_variance": bool(p_lev > 0.05),
            "justification": (
                "Data violates normality assumption (Shapiro-Wilk p < 0.05). "
                "Non-parametric Mann-Whitney U test is strictly required."
                if not is_normal else
                "Data satisfied normality assumption (Shapiro-Wilk p >= 0.05)."
            )
        }
        return diagnostics

    def compute_descriptive_stats(self) -> pd.DataFrame:
        """
        Computes robust non-parametric descriptive statistics (Median, IQR Q1-Q3)
        grouped by Subject, Repo Size, and Domain.
        """
        grouped = self.df.groupby(["subject", "repo_size", "repo_domain"])
        rows = []

        for name, group in grouped:
            subj, size, dom = name
            for metric in ["lvc", "lvc_norm", "cnlv", "dged"]:
                vals = group[metric].dropna()
                q1 = vals.quantile(0.25)
                q3 = vals.quantile(0.75)
                iqr = q3 - q1

                rows.append({
                    "subject": subj,
                    "repo_size": size,
                    "repo_domain": dom,
                    "metric": metric,
                    "count": len(vals),
                    "median": float(vals.median()),
                    "q1": float(q1),
                    "q3": float(q3),
                    "iqr": float(iqr),
                    "mean": float(vals.mean()),
                    "std": float(vals.std()) if len(vals) > 1 else 0.0
                })

        return pd.DataFrame(rows)

    def run_mann_whitney_u_test(self, metric: str = "cnlv") -> Dict[str, Any]:
        """
        Performs Mann-Whitney U test comparing Agent vs. Human drift distributions.
        Computes Rank-Biserial Correlation (r_rb) effect size.
        """
        agent_vals = self.df[self.df["subject"] == "agent"][metric].dropna()
        human_vals = self.df[self.df["subject"] == "human"][metric].dropna()

        n1, n2 = len(agent_vals), len(human_vals)
        u_stat, p_val = stats.mannwhitneyu(agent_vals, human_vals, alternative="greater")

        # Rank-Biserial Correlation r_rb = 1 - (2U / (n1 * n2))
        r_rb = 1.0 - (2.0 * u_stat / (n1 * n2))
        
        # Effect size classification (Cohen / Rosenthal bounds)
        abs_r = abs(r_rb)
        if abs_r < 0.1:
            effect_class = "Negligible"
        elif abs_r < 0.3:
            effect_class = "Small"
        elif abs_r < 0.5:
            effect_class = "Medium"
        else:
            effect_class = "Large"

        return {
            "metric": metric,
            "n_agent": n1,
            "n_human": n2,
            "mann_whitney_u": float(u_stat),
            "p_value": float(p_val),
            "significant_alpha_05": bool(p_val < 0.05),
            "rank_biserial_r": float(r_rb),
            "effect_size_magnitude": effect_class,
            "median_agent": float(agent_vals.median()),
            "median_human": float(human_vals.median())
        }

    def fit_mixed_effects_model(self, metric: str = "cnlv") -> Dict[str, Any]:
        """
        Fits Linear Mixed-Effects Model (LMM):
        metric ~ step_idx + (1 | repo_id)
        Fixed effect: Session step index (trajectory trend)
        Random effect: Repository ID (accounts for repo-level variance)
        """
        agent_df = self.df[self.df["subject"] == "agent"].copy()
        
        # Fit MixedLM
        model = smf.mixedlm(f"{metric} ~ step_idx", agent_df, groups=agent_df["repo_id"])
        result = model.fit()

        fixed_slope = float(result.params["step_idx"])
        p_val = float(result.pvalues["step_idx"])
        conf_int = result.conf_int().loc["step_idx"].tolist()
        random_var = float(result.cov_re.iloc[0, 0])

        return {
            "formula": f"{metric} ~ step_idx + (1 | repo_id)",
            "n_obs": int(result.nobs),
            "fixed_effect_slope": fixed_slope,
            "fixed_effect_pvalue": p_val,
            "conf_int_95": conf_int,
            "random_effect_var": random_var,
            "interpretation": (
                f"For each sequential agent session, {metric} increases by {fixed_slope:.4f} units "
                f"(p = {p_val:.4e}, random repo variance = {random_var:.4f})."
            )
        }

    def compute_power_analysis(self, n1: int, n2: int, alpha: float = 0.05, power: float = 0.80) -> Dict[str, Any]:
        """
        Calculates Minimum Detectable Effect Size (MDES) given sample size.
        """
        # Analytical approximation for two-sample test MDES (Cohen's d)
        # d_mdes = (z_alpha + z_beta) * sqrt((n1 + n2) / (n1 * n2))
        z_alpha = stats.norm.ppf(1 - alpha / 2)
        z_beta = stats.norm.ppf(power)
        
        mdes_d = (z_alpha + z_beta) * np.sqrt((n1 + n2) / (n1 * n2))

        is_adequately_powered = (n1 >= 15 and n2 >= 15)

        return {
            "n_agent_samples": n1,
            "n_human_samples": n2,
            "alpha": alpha,
            "target_power": power,
            "mdes_cohens_d": float(mdes_d),
            "is_adequately_powered": is_adequately_powered,
            "power_assessment": (
                f"Sample size (N1={n1}, N2={n2}) provides 80% power to detect effect sizes d >= {mdes_d:.3f}."
                if is_adequately_powered else
                f"WARNING: Sample size (N1={n1}, N2={n2}) is underpowered. Minimum detectable effect size is d = {mdes_d:.3f}. "
                "Caution required when interpreting non-significant findings."
            )
        }

    def fit_firth_logistic(self, X: np.ndarray, y: np.ndarray) -> Tuple[np.ndarray, np.ndarray, np.ndarray]:
        """
        Fits Firth's penalized logistic regression using scipy.optimize to handle
        complete or quasi-complete separation.
        """
        import scipy.optimize as opt
        n, p = X.shape
        
        def log_like_penalized(beta):
            eta = np.clip(X @ beta, -100, 100)
            prob = 1.0 / (1.0 + np.exp(-eta))
            eps = 1e-15
            log_l = np.sum(y * np.log(prob + eps) + (1.0 - y) * np.log(1.0 - prob + eps))
            
            # Fisher Info matrix
            W = prob * (1.0 - prob)
            W = np.clip(W, 1e-7, 0.25)
            I_mat = X.T @ (W[:, np.newaxis] * X)
            
            sign, log_det = np.linalg.slogdet(I_mat)
            penalty = 0.5 * log_det
            return -(log_l + penalty)

        beta_init = np.zeros(p)
        res = opt.minimize(log_like_penalized, beta_init, method="BFGS")
        beta_fit = res.x
        
        # Standard errors from inverse Fisher Info matrix
        eta_fit = np.clip(X @ beta_fit, -100, 100)
        prob_fit = 1.0 / (1.0 + np.exp(-eta_fit))
        W_fit = prob_fit * (1.0 - prob_fit)
        W_fit = np.clip(W_fit, 1e-7, 0.25)
        I_mat_fit = X.T @ (W_fit[:, np.newaxis] * X)
        
        try:
            cov_matrix = np.linalg.inv(I_mat_fit)
            se = np.sqrt(np.diag(cov_matrix))
        except np.linalg.LinAlgError:
            se = np.full(p, np.nan)
            
        z_stats = np.where(se > 0, beta_fit / se, 0.0)
        p_values = 2.0 * (1.0 - stats.norm.cdf(np.abs(z_stats)))
        
        return beta_fit, se, p_values

    def run_domain_stratified_tests(self, metric: str = "cnlv") -> pd.DataFrame:
        """
        Runs Mann-Whitney U tests comparing agent vs. human stratified by application domain,
        and applies Bonferroni and Benjamini-Hochberg FDR corrections.
        """
        results = []
        domains = self.df["repo_domain"].unique()
        
        for dom in domains:
            agent_vals = self.df[(self.df["subject"] == "agent") & (self.df["repo_domain"] == dom)][metric].dropna()
            human_vals = self.df[(self.df["subject"] == "human") & (self.df["repo_domain"] == dom)][metric].dropna()
            
            n_agent = len(agent_vals)
            n_human = len(human_vals)
            
            if n_agent > 0 and n_human > 0:
                u_stat, p_val = stats.mannwhitneyu(agent_vals, human_vals, alternative="greater")
                r_rb = 1.0 - (2.0 * u_stat / (n_agent * n_human)) if n_agent * n_human > 0 else 0.0
            else:
                u_stat, p_val, r_rb = 0.0, 1.0, 0.0
                
            results.append({
                "domain": dom,
                "n_agent": n_agent,
                "n_human": n_human,
                "u_stat": float(u_stat),
                "p_raw": float(p_val),
                "r_rb": float(r_rb)
            })
            
        res_df = pd.DataFrame(results)
        
        # Apply corrections
        m = len(res_df)
        if m > 0:
            res_df["p_bonferroni"] = np.minimum(res_df["p_raw"] * m, 1.0)
            
            # Sort by p_raw for BH FDR
            res_df = res_df.sort_values("p_raw").reset_index(drop=True)
            res_df["rank"] = np.arange(1, m + 1)
            res_df["p_bh"] = res_df["p_raw"] * m / res_df["rank"]
            
            # Enforce monotonicity
            bh_vals = []
            for idx in range(m):
                bh_vals.append(res_df.loc[idx:, "p_bh"].min())
            res_df["p_bh"] = np.minimum(bh_vals, 1.0)
            res_df = res_df.drop(columns=["rank"])
            
        return res_df

    def run_downstream_risk_analysis(self) -> Dict[str, Any]:
        """
        Evaluates Spearman Rank Correlation between CNLV and test failure,
        and fits logistic regression to quantify odds ratio.
        Detects complete/quasi-complete separation and applies Firth's correction if needed.
        """
        agent_df = self.df[self.df["subject"] == "agent"].copy()
        
        corr, p_corr = stats.spearmanr(agent_df["cnlv"], agent_df["task_failed"])

        y = agent_df["task_failed"].values
        if len(np.unique(y)) < 2:
            return {
                "spearman_rho": float(corr),
                "spearman_pvalue": float(p_corr),
                "separation_detected": False,
                "model_type": "None (no variance in outcome)",
                "logit_cnlv_beta": 0.0,
                "odds_ratio": 1.0,
                "logit_pvalue": 1.0,
                "or_lower_95": 1.0,
                "or_upper_95": 1.0,
                "ci_absurdly_wide": False,
                "practical_hook_summary": "No variance in task outcomes; logistic regression skipped."
            }

        X = sm.add_constant(agent_df["cnlv"].values)

        separation_detected = False
        mle_failed = False
        try:
            logit_mod = sm.Logit(y, X).fit(disp=False)
            if np.any(logit_mod.bse > 50.0) or np.any(np.isnan(logit_mod.bse)):
                separation_detected = True
        except Exception:
            separation_detected = True
            mle_failed = True

        if separation_detected:
            beta, se, p_values = self.fit_firth_logistic(X, y)
            model_type = "Firth Penalized Logistic"
            beta_cnlv = beta[1]
            se_cnlv = se[1]
            p_logit = p_values[1]
        else:
            model_type = "Standard MLE Logistic"
            beta_cnlv = logit_mod.params[1]
            se_cnlv = logit_mod.bse[1]
            p_logit = logit_mod.pvalues[1]

        odds_ratio = np.exp(beta_cnlv)
        z_crit = 1.96
        ci_lower = np.exp(beta_cnlv - z_crit * se_cnlv)
        ci_upper = np.exp(beta_cnlv + z_crit * se_cnlv)

        ci_absurdly_wide = bool(ci_upper > 1e6 or (ci_upper / max(1e-15, ci_lower)) > 1000.0)

        summary_text = (
            f"Architectural drift (CNLV) predicts downstream task test failure "
            f"({model_type}: Odds Ratio = {odds_ratio:.2e}, 95% CI = [{ci_lower:.2e}, {ci_upper:.2e}], p = {p_logit:.4e})."
        )
        if ci_absurdly_wide:
            summary_text += " WARNING: The confidence interval is extremely wide due to complete/quasi-complete separation constraints."

        return {
            "spearman_rho": float(corr),
            "spearman_pvalue": float(p_corr),
            "separation_detected": separation_detected,
            "model_type": model_type,
            "logit_cnlv_beta": float(beta_cnlv),
            "odds_ratio": float(odds_ratio),
            "logit_pvalue": float(p_logit),
            "or_lower_95": float(ci_lower),
            "or_upper_95": float(ci_upper),
            "ci_absurdly_wide": ci_absurdly_wide,
            "practical_hook_summary": summary_text
        }
