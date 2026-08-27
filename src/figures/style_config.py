import matplotlib.pyplot as plt
import seaborn as sns

def set_publication_style():
    """
    Sets elite IEEE/ACM journal & conference publication style:
    - High-contrast, colorblind-safe Nature/IEEE tier color palette
    - Crisp serif typography with optimal font scaling for multi-column papers
    - True vector PDF/SVG rendering (font type 42 / TrueType embedding)
    - Clean visual hierarchy with zero clutter
    """
    plt.rcParams.update({
        "font.family": "serif",
        "font.serif": ["DejaVu Serif", "Times New Roman", "Times", "Liberation Serif"],
        "mathtext.fontset": "stix",  # High-quality LaTeX math typography
        "font.size": 11,
        "axes.labelsize": 11.5,
        "axes.titlesize": 12,
        "legend.fontsize": 10,
        "xtick.labelsize": 10,
        "ytick.labelsize": 10,
        "figure.titlesize": 13,
        "axes.labelweight": "bold",
        "axes.titleweight": "bold",
        "axes.spines.top": False,
        "axes.spines.right": False,
        "axes.linewidth": 1.2,
        "axes.grid": True,
        "grid.alpha": 0.25,
        "grid.color": "#B0BEC5",
        "grid.linestyle": "--",
        "grid.linewidth": 0.7,
        "figure.autolayout": True,
        "pdf.fonttype": 42,
        "ps.fonttype": 42,
        "svg.fonttype": "none",
        "savefig.dpi": 600,
        "savefig.bbox": "tight",
        "savefig.pad_inches": 0.05
    })

    # Elite Publication Colorblind-Safe Palette (Okabe-Ito / IEEE / Nature Tier)
    PALETTE = {
        "agent": "#D55E00",       # Vermilion / Deep Crimson-Orange (Agent)
        "agent_light": "#FDEBE7", # Soft Vermilion tint
        "human": "#0072B2",       # Deep Royal Blue (Human Baseline)
        "human_light": "#E6F2FF", # Soft Royal Blue tint
        "accent": "#009E73",      # Emerald Green
        "warning": "#E69F00",     # Amber Yellow
        "purple": "#7570B3",      # Slate Purple
        "dark": "#1A1A1A",        # Charcoal / Off-black for text
        "grid": "#E0E0E0",        # Light grey grid
        "card_bg": "#FAFAFA"      # Background card fill
    }

    sns.set_palette([PALETTE["agent"], PALETTE["human"], PALETTE["accent"]])
    return PALETTE
