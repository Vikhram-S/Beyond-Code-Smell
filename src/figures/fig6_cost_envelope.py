import json
from pathlib import Path
import numpy as np
import matplotlib.pyplot as plt
from src.figures.style_config import set_publication_style


def render_fig6_cost_envelope(output_dir: Path):
    """Token/request envelope from real cost_summary.json files (free-tier Gemini)."""
    palette = set_publication_style()
    output_dir.mkdir(parents=True, exist_ok=True)

    calls = []
    for summary in Path("checkpoints").rglob("cost_summary.json"):
        try:
            data = json.loads(summary.read_text(encoding="utf-8"))
        except Exception:
            continue
        calls.extend(data.get("call_history") or [])

    if not calls:
        raise FileNotFoundError(
            "No cost_summary.json call_history found. Run the Gemini pipeline before Fig 6."
        )

    sessions = np.arange(1, len(calls) + 1)
    tokens = np.cumsum([c.get("input_tokens", 0) + c.get("output_tokens", 0) for c in calls])
    tokens_k = tokens / 1000.0

    fig, ax1 = plt.subplots(figsize=(7.2, 4.0), dpi=600)
    ax1.fill_between(sessions, 0, tokens_k, color=palette["agent"], alpha=0.12)
    line1 = ax1.plot(
        sessions, tokens_k, color=palette["agent"], lw=2.4, label="Cumulative tokens (thousands)"
    )
    ax1.set_xlabel("Cumulative Gemini generateContent calls", fontsize=10, fontweight="bold")
    ax1.set_ylabel("Cumulative tokens (thousands)", fontsize=10.5, fontweight="bold")
    ax1.set_title(
        "Figure 6 (Appendix): Gemini free-tier token envelope (USD = 0 by construction)",
        fontsize=11, fontweight="bold", pad=12,
    )
    ax1.legend(loc="upper left", frameon=True, facecolor="#FAFAFA", edgecolor="#CCCCCC", fontsize=8.8)
    plt.tight_layout()
    for fmt, dpi in (("pdf", None), ("svg", None), ("png", 600)):
        kwargs = {"format": fmt, "bbox_inches": "tight"}
        if dpi:
            kwargs["dpi"] = dpi
        plt.savefig(output_dir / f"fig6_cost_envelope.{fmt}", **kwargs)
    plt.close()
    print(f"Rendered Fig 6 from real token logs: {output_dir / 'fig6_cost_envelope.pdf'}")
