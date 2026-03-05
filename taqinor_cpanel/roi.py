from io import BytesIO

import matplotlib.pyplot as plt
import numpy as np

from constants import BLUE_MAIN, ORANGE_ACCENT, MOIS, GHI, DAYS_IN_MONTH, EFFICIENCY, KWH_PRICE


# ---------- GRAPHIQUES TAQINOR ----------
def taqinor_graph_style():
    plt.rcParams.update(
        {
            "font.size": 9,
            "axes.titlesize": 11,
            "axes.labelsize": 9,
            "xtick.labelsize": 8,
            "ytick.labelsize": 8,
            "legend.fontsize": 8,
        }
    )


def interpoler_factures(hiver, ete):
    if ete == 0:
        return [hiver] * 12
    premiere = [hiver + (ete - hiver) / 6 * i for i in range(7)]
    seconde = [ete - (ete - hiver) / 4 * i for i in range(5)]
    return [*premiere, *seconde]


def build_roi_figure(mois, factures, eco_sans, eco_avec):
    """
    Chart: background bars = facture sans PV, dashed lines with markers for économies SANS/AVEC.
    """
    taqinor_graph_style()
    fig, ax = plt.subplots(figsize=(6.0, 3.0), dpi=120)
    x = np.arange(len(mois))

    # Colors
    import matplotlib.colors as mcolors

    def _to_hex(c):
        try:
            return mcolors.to_hex(c)
        except Exception:
            return str(c)

    bar_color = "#A6C8E5"
    color_sans = _to_hex(BLUE_MAIN)
    color_avec = "#F4A300"

    monthly_bill_no_pv = factures if isinstance(factures, (list, tuple)) else list(factures)

    # Background bars for facture sans PV
    ax.bar(
        x,
        monthly_bill_no_pv,
        width=0.9,
        color=bar_color,
        alpha=0.7,
        label="Facture sans PV",
        zorder=1,
    )

    # Savings curves
    ax.plot(
        x,
        eco_sans,
        linestyle="--",
        linewidth=2.0,
        marker="o",
        markersize=4,
        color=color_sans,
        label="Économie mensuelle – SANS batterie",
        zorder=2,
    )

    ax.plot(
        x,
        eco_avec,
        linestyle="--",
        linewidth=2.0,
        marker="s",
        markersize=4,
        color=color_avec,
        label="Économie mensuelle – AVEC batterie",
        zorder=3,
    )

    ax.set_xticks(x)
    ax.set_xticklabels(mois)
    ax.spines["top"].set_visible(False)
    ax.spines["right"].set_visible(False)
    ax.yaxis.grid(True, linestyle="--", alpha=0.25)
    ax.xaxis.grid(False)
    ax.set_ylabel("Montant (MAD)")
    ax.set_title("Estimation des économies mensuelles", fontsize=11)

    legend = ax.legend(fontsize=8, loc="upper right", frameon=True)
    legend.get_frame().set_alpha(0.9)

    ax.margins(y=0.1)
    plt.tight_layout()
    return fig


def roi_figure_buffer(mois, factures, eco_sans, eco_avec):
    fig = build_roi_figure(mois, factures, eco_sans, eco_avec)
    buf = BytesIO()
    fig.savefig(buf, format="png", dpi=300, bbox_inches="tight")
    plt.close(fig)
    buf.seek(0)
    return buf


def find_break_even_year(cumulative_values, years):
    for year, value in zip(years, cumulative_values):
        if value >= 0:
            return year, value
    return None, None


def build_roi_cumulative_figure(years, cumulative_sans, cumulative_avec=None):
    taqinor_graph_style()
    fig, ax = plt.subplots(figsize=(6.5, 3.2), dpi=120)
    x = np.array(years)

    color_sans = BLUE_MAIN
    color_avec = "#F4A300"

    fig.patch.set_facecolor("white")
    ax.set_facecolor("white")

    ax.plot(
        x,
        cumulative_sans,
        linewidth=2.4,
        marker="o",
        markersize=4,
        color=color_sans,
        label="Sans batterie",
    )
    ax.fill_between(
        x,
        cumulative_sans,
        [0] * len(cumulative_sans),
        color=color_sans,
        alpha=0.06,
    )

    if cumulative_avec is not None:
        ax.plot(
            x,
            cumulative_avec,
            linewidth=2.0,
            linestyle="--",
            marker="o",
            markersize=3,
            color=color_avec,
            label="Avec batterie",
        )
        ax.fill_between(
            x,
            cumulative_avec,
            [0] * len(cumulative_avec),
            color=color_avec,
            alpha=0.04,
        )

    ax.spines["top"].set_visible(False)
    ax.spines["right"].set_visible(False)
    ax.yaxis.grid(True, linestyle="--", alpha=0.3)
    ax.xaxis.grid(False)

    ax.set_xticks([0, 5, 10, 15, 20, 25])
    ax.set_xlabel("Années")
    ax.set_ylabel("Gain cumulé (MAD)")
    ax.set_title("Projection des gains cumulés sur 25 ans", fontsize=11)
    ax.legend(fontsize=8, loc="upper left", frameon=False)

    be_year_sans, be_val_sans = find_break_even_year(cumulative_sans, years)
    if be_year_sans is not None:
        ax.scatter(be_year_sans, be_val_sans, color=color_sans, s=30, zorder=3)
        ax.annotate(
            f"ROI ~ {be_year_sans} ans",
            xy=(be_year_sans, be_val_sans),
            xytext=(be_year_sans + 0.5, be_val_sans * 1.05 if be_val_sans != 0 else 0),
            textcoords="data",
            fontsize=7,
            color=color_sans,
            arrowprops=dict(arrowstyle="->", linewidth=0.8, color=color_sans),
            ha="left",
            va="bottom",
        )

    if cumulative_avec is not None:
        be_year_avec, be_val_avec = find_break_even_year(cumulative_avec, years)
        if be_year_avec is not None:
            ax.scatter(be_year_avec, be_val_avec, color=color_avec, s=30, zorder=3)
            ax.annotate(
                f"ROI ~ {be_year_avec} ans",
                xy=(be_year_avec, be_val_avec),
                xytext=(be_year_avec + 0.5, be_val_avec * 1.05 if be_val_avec != 0 else 0),
                textcoords="data",
                fontsize=7,
                color=color_avec,
                arrowprops=dict(arrowstyle="->", linewidth=0.8, color=color_avec),
                ha="left",
                va="bottom",
            )

    plt.tight_layout()
    return fig


def roi_cumulative_buffer(years, cumulative_sans, cumulative_avec=None):
    fig = build_roi_cumulative_figure(years, cumulative_sans, cumulative_avec)
    buf = BytesIO()
    fig.savefig(buf, format="png", dpi=300, bbox_inches="tight")
    plt.close(fig)
    buf.seek(0)
    return buf


def create_monthly_savings_chart(months, monthly_sans, monthly_avec):
    """
    months: liste de labels ["Jan", "Fév", ...]
    monthly_sans: liste de 12 valeurs (économies mensuelles scénario SANS batterie)
    monthly_avec: liste de 12 valeurs (économies mensuelles scénario AVEC batterie)
    Retourne un buffer PNG (BytesIO) utilisable par ReportLab.Image.
    """
    taqinor_graph_style()
    fig, ax = plt.subplots(figsize=(6, 2.6))

    x = range(len(months))
    width = 0.35

    bars_sans = ax.bar(
        [i - width / 2 for i in x],
        monthly_sans,
        width=width,
        label="Sans batterie",
        color=BLUE_MAIN,
    )
    bars_avec = ax.bar(
        [i + width / 2 for i in x],
        monthly_avec,
        width=width,
        label="Avec batterie",
        color=ORANGE_ACCENT,
    )

    ax.set_title("Économies mensuelles estimées")
    ax.set_ylabel("Économies mensuelles (MAD)")
    ax.set_xticks(list(x))
    ax.set_xticklabels(months)
    ax.set_axisbelow(True)
    ax.set_ylim(bottom=0)
    ax.margins(y=0.05)

    for spine in ["top", "right"]:
        ax.spines[spine].set_visible(False)
    ax.grid(axis="y", alpha=0.25, linestyle="--")

    for bar in list(bars_sans) + list(bars_avec):
        height = bar.get_height()
        ax.text(
            bar.get_x() + bar.get_width() / 2,
            height + 10,
            f"{int(round(height))}",
            ha="center",
            va="bottom",
            fontsize=7,
        )

    ax.legend(frameon=False, loc="upper left")

    plt.tight_layout()

    buf = BytesIO()
    fig.savefig(buf, format="png", dpi=150)
    plt.close(fig)
    buf.seek(0)
    return buf


def create_monthly_production_chart(months, production_kwh):
    """
    months: liste de labels de mois, ex: ['Jan', 'Fév', ...]
    production_kwh: liste de valeurs mensuelles en kWh
    Retourne un buffer d'image PNG (BytesIO) prêt à être utilisé par ReportLab.
    """
    fig, ax = plt.subplots(figsize=(6, 3))

    ax.bar(months, production_kwh)
    ax.set_ylabel("Production (kWh)")
    ax.set_title("Production annuelle estimée par mois")
    ax.grid(axis="y", alpha=0.3)

    plt.tight_layout()

    buf = BytesIO()
    fig.savefig(buf, format="png", dpi=150)
    plt.close(fig)
    buf.seek(0)
    return buf


def create_cumulative_savings_chart(years, yearly_savings):
    """
    years: liste des années, ex: [1, 2, ..., 20]
    yearly_savings: liste des économies annuelles (MAD/an)
    Affiche la courbe des économies cumulées sur la durée.
    """
    cumulative = []
    total = 0
    for val in yearly_savings:
        total += val
        cumulative.append(total)

    fig, ax = plt.subplots(figsize=(6, 3))

    ax.plot(years, cumulative, marker="o")
    ax.set_xlabel("Années")
    ax.set_ylabel("Économies cumulées (MAD)")
    ax.set_title("Projection des économies cumulées sur 20 ans")
    ax.grid(True, alpha=0.3)

    plt.tight_layout()

    buf = BytesIO()
    fig.savefig(buf, format="png", dpi=150)
    plt.close(fig)
    buf.seek(0)
    return buf
