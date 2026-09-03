import json
import numpy as np
import pandas as pd
import matplotlib.pyplot as plt
import seaborn as sns
from pathlib import Path
from src.figures.style_config import set_publication_style


LAYER_ORDER = ["L1_domain", "L2_service", "L3_adapter", "L4_entrypoint"]
LAYER_LABELS = [
    "Layer 1: Domain Core",
    "Layer 2: Service / Application",
    "Layer 3: Infrastructure / Adapter",
    "Layer 4: API / Entrypoint",
]


def _count_from_checkpoints(checkpoint_dir: Path) -> np.ndarray:
    mat = np.zeros((4, 4), dtype=int)
    idx = {k: i for i, k in enumerate(LAYER_ORDER)}
    if not checkpoint_dir.exists():
        return mat
    for file in checkpoint_dir.rglob("session_*.json"):
        try:
            data = json.loads(file.read_text(encoding="utf-8"))
        except Exception:
            continue
        for v in data.get("violations") or []:
            desc = str(v.get("description", ""))
            src = tgt = None
            for layer in LAYER_ORDER:
                if f"({layer})" in desc:
                    if src is None:
                        src = layer
                    else:
                        tgt = layer
            if src in idx and tgt in idx:
                mat[idx[src], idx[tgt]] += 1
    return mat


def render_fig4_violation_heatmap(data_path: Path, output_dir: Path):
    palette = set_publication_style()
    output_dir.mkdir(parents=True, exist_ok=True)

    violation_matrix = _count_from_checkpoints(Path("checkpoints"))
    heatmap_df = pd.DataFrame(violation_matrix, index=LAYER_LABELS, columns=LAYER_LABELS)

    fig, ax = plt.subplots(figsize=(6.8, 4.5), dpi=600)
    sns.heatmap(
        heatmap_df,
        annot=True,
        fmt="d",
        cmap="YlOrRd",
        cbar_kws={"label": "Layer Boundary Violation Frequency Count", "shrink": 0.8},
        ax=ax,
    )
    ax.set_title(
        "Figure 4: Illegal layer crossings counted from saved session checkpoints",
        fontsize=11, fontweight="bold", pad=12,
    )
    plt.tight_layout()
    for fmt in ("pdf", "svg"):
        plt.savefig(output_dir / f"fig4_violation_heatmap.{fmt}", format=fmt, bbox_inches="tight")
    plt.savefig(output_dir / "fig4_violation_heatmap.png", format="png", dpi=600, bbox_inches="tight")
    plt.close()
    print(f"[Fig4] Rendered from checkpoints: {output_dir / 'fig4_violation_heatmap.pdf'}")
