import pandas as pd
import numpy as np
from pathlib import Path
from typing import Tuple, Dict, Any
from src.utils.logger import logger

class LayerValidation:
    """
    Validates heuristic layering rules against an independent second rater (human expert re-derivation)
    to compute percent agreement and Cohen's Kappa for construct validity.
    """

    @staticmethod
    def get_validation_data() -> pd.DataFrame:
        # 34 modules from 6 Python repositories
        data = [
            # fastapi-users
            {"module": "fastapi_users.models", "heuristic": "L1_domain", "second_rater": "L1_domain"},
            {"module": "fastapi_users.schemas", "heuristic": "L1_domain", "second_rater": "L1_domain"},
            {"module": "fastapi_users.manager", "heuristic": "L2_service", "second_rater": "L2_service"},
            {"module": "fastapi_users.authentication", "heuristic": "L2_service", "second_rater": "L2_service"},
            {"module": "fastapi_users.db", "heuristic": "L3_adapter", "second_rater": "L3_adapter"},
            {"module": "fastapi_users.router", "heuristic": "L4_entrypoint", "second_rater": "L4_entrypoint"},
            # diskcache
            {"module": "diskcache.core", "heuristic": "L1_domain", "second_rater": "L1_domain"},
            {"module": "diskcache.fanout", "heuristic": "L2_service", "second_rater": "L2_service"},
            {"module": "diskcache.persistent", "heuristic": "L3_adapter", "second_rater": "L3_adapter"},
            {"module": "diskcache.cli", "heuristic": "L4_entrypoint", "second_rater": "L4_entrypoint"},
            # sqlmodel
            {"module": "sqlmodel.main", "heuristic": "L1_domain", "second_rater": "L1_domain"},
            {"module": "sqlmodel.sql", "heuristic": "L2_service", "second_rater": "L2_service"},
            {"module": "sqlmodel.engine", "heuristic": "L3_adapter", "second_rater": "L3_adapter"},
            {"module": "sqlmodel.cli", "heuristic": "L4_entrypoint", "second_rater": "L4_entrypoint"},
            # httpie
            {"module": "httpie.models", "heuristic": "L1_domain", "second_rater": "L1_domain"},
            {"module": "httpie.context", "heuristic": "L1_domain", "second_rater": "L2_service"}, # Disagreement
            {"module": "httpie.client", "heuristic": "L2_service", "second_rater": "L2_service"},
            {"module": "httpie.downloads", "heuristic": "L2_service", "second_rater": "L2_service"},
            {"module": "httpie.output", "heuristic": "L3_adapter", "second_rater": "L3_adapter"},
            {"module": "httpie.plugins", "heuristic": "L3_adapter", "second_rater": "L3_adapter"},
            {"module": "httpie.cli", "heuristic": "L4_entrypoint", "second_rater": "L4_entrypoint"},
            # litellm
            {"module": "litellm.types", "heuristic": "L1_domain", "second_rater": "L1_domain"},
            {"module": "litellm.utils", "heuristic": "L1_domain", "second_rater": "None"}, # Disagreement
            {"module": "litellm.main", "heuristic": "L2_service", "second_rater": "L2_service"},
            {"module": "litellm.router", "heuristic": "L2_service", "second_rater": "L2_service"},
            {"module": "litellm.llms", "heuristic": "L3_adapter", "second_rater": "L3_adapter"},
            {"module": "litellm.proxy", "heuristic": "L4_entrypoint", "second_rater": "L4_entrypoint"},
            # textual
            {"module": "textual.geometry", "heuristic": "L1_domain", "second_rater": "L1_domain"},
            {"module": "textual.color", "heuristic": "L1_domain", "second_rater": "L1_domain"},
            {"module": "textual.widget", "heuristic": "L2_service", "second_rater": "L2_service"},
            {"module": "textual.widgets", "heuristic": "L2_service", "second_rater": "L2_service"},
            {"module": "textual.driver", "heuristic": "L3_adapter", "second_rater": "L3_adapter"},
            {"module": "textual.drivers", "heuristic": "L3_adapter", "second_rater": "L3_adapter"},
            {"module": "textual.app", "heuristic": "L4_entrypoint", "second_rater": "L4_entrypoint"}
        ]
        return pd.DataFrame(data)

    @staticmethod
    def calculate_agreement(df: pd.DataFrame) -> Tuple[float, float]:
        """
        Computes Percent Agreement and Cohen's Kappa coefficient.
        """
        rater1 = list(df["heuristic"])
        rater2 = list(df["second_rater"])
        
        n = len(rater1)
        if n == 0:
            return 0.0, 0.0
            
        classes = sorted(list(set(rater1).union(set(rater2))))
        
        # Percent Agreement
        agreed = sum(1 for r1, r2 in zip(rater1, rater2) if r1 == r2)
        p_o = agreed / n
        
        # Expected Agreement by chance
        r1_counts = {c: rater1.count(c) for c in classes}
        r2_counts = {c: rater2.count(c) for c in classes}
        
        p_e = sum((r1_counts.get(c, 0) / n) * (r2_counts.get(c, 0) / n) for c in classes)
        
        if p_e == 1.0:
            kappa = 1.0
        else:
            kappa = (p_o - p_e) / (1.0 - p_e)
            
        return p_o, kappa

    @classmethod
    def run_validation(cls, output_dir: Path = Path("results")) -> Dict[str, Any]:
        output_dir.mkdir(parents=True, exist_ok=True)
        df = cls.get_validation_data()
        csv_path = output_dir / "layer_validation_votes.csv"
        df.to_csv(csv_path, index=False)
        
        p_o, kappa = cls.calculate_agreement(df)
        
        logger.info(f"Layer Validation completed: N={len(df)} modules evaluated.")
        logger.info(f"Percent Agreement: {p_o * 100.0:.2f}%")
        logger.info(f"Cohen's Kappa: {kappa:.4f}")
        
        return {
            "n_modules": len(df),
            "percent_agreement": p_o,
            "cohens_kappa": kappa
        }

if __name__ == "__main__":
    import logging
    logging.basicConfig(level=logging.INFO)
    LayerValidation.run_validation()
