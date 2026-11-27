"""Every table and figure of the results, from results.json only (analyse.py). Nothing is typed by hand.

Usage: python make_figures.py results.json <out folder>
Writes table_tools.csv, table_cohorts.csv, table_agreement.csv, figure_tools.png/.pdf, figure_cohorts.png/.pdf.
Colours: Okabe & Ito (2008) colour-blind-safe set, one fixed colour per tool; the 12% margin is a dashed grey line.
"""
import csv
import json
import sys
from pathlib import Path

import matplotlib
matplotlib.use("Agg")
import matplotlib.pyplot as plt

TOOLS = ("FLAMeS", "LST-AI", "MindGlide", "WMH-SynthSeg", "SAMSEG")
COLOUR = dict(zip(TOOLS, ("#0072B2", "#E69F00", "#009E73", "#CC79A7", "#56B4E9")))
MARGIN = 0.12
INK, MUTED = "#1a1a1a", "#6b6b6b"


def pct(v):
    return f"{100 * v:.1f}"


def tools_table(r, out):
    with open(out / "table_tools.csv", "w", newline="", encoding="utf-8") as f:
        w = csv.writer(f)
        w.writerow(["age group", "tool", "positive", "completed", "failed", "percent", "95% low", "95% high", "reading",
                    "if failures negative", "if failures positive"])
        for group, key in (("<50", "tools_under_50"), (">=50", "tools_50_or_more")):
            for t in TOOLS:
                v = r[key][t]
                if not v["n"]:
                    w.writerow([group, t, 0, 0, v["failed"], "", "", "", "", "", ""])
                    continue
                neg, posv = v.get("all_failed_negative"), v.get("all_failed_positive")
                w.writerow([group, t, v["x"], v["n"], v["failed"], pct(v["p"]), pct(v["low"]), pct(v["high"]),
                            v["reading"] if group == "<50" else "", pct(neg[0]) if neg else "", pct(posv[0]) if posv else ""])


def cohorts_table(r, out):
    with open(out / "table_cohorts.csv", "w", newline="", encoding="utf-8") as f:
        w = csv.writer(f)
        w.writerow(["cohort and age group", "FLAMeS positive", "completed", "failed", "percent", "95% low", "95% high"])
        for c, v in r["primary_by_cohort"].items():
            w.writerow([c, v["x"], v["n"], v["failed"], *(pct(v[k]) for k in ("p", "low", "high"))] if v["n"] else
                       [c, 0, 0, v["failed"], "", "", ""])


def agreement_table(r, out):
    with open(out / "table_agreement.csv", "w", newline="", encoding="utf-8") as f:
        w = csv.writer(f)
        w.writerow(["age group", "people with all tools", "tools disagree", "percent", "Fleiss kappa", "kappa 95% low", "kappa 95% high"])
        for group, key in (("<50", "agreement_under_50"), (">=50", "agreement_50_or_more")):
            a = r[key]
            if a["n"]:
                w.writerow([group, a["n"], a["discordant"], pct(a["p"]), f"{a['kappa']:.2f}",
                            f"{a['kappa_interval'][0]:.2f}", f"{a['kappa_interval'][1]:.2f}"])


def style(ax):
    for side in ("top", "right"):
        ax.spines[side].set_visible(False)
    for side in ("left", "bottom"):
        ax.spines[side].set_color(MUTED)
    ax.tick_params(colors=MUTED, labelcolor=INK, labelsize=9)
    ax.grid(axis="x", color="#e6e6e6", linewidth=0.8)
    ax.set_axisbelow(True)


def tools_figure(r, out):
    fig, axes = plt.subplots(1, 2, figsize=(7.2, 3.2), sharey=True)
    for ax, (title, key) in zip(axes, (("Under 50 (primary)", "tools_under_50"), ("50 or more", "tools_50_or_more"))):
        style(ax)
        for i, t in enumerate(TOOLS):
            v = r[key][t]
            if not v["n"]:
                continue
            y = len(TOOLS) - 1 - i
            ax.plot([100 * v["low"], 100 * v["high"]], [y, y], color=COLOUR[t], linewidth=2, solid_capstyle="round")
            ax.plot(100 * v["p"], y, "o", color=COLOUR[t], markersize=7, markeredgecolor="white", markeredgewidth=1.5)
            ax.text(100 * v["high"] + 1.5, y, f"{v['x']}/{v['n']}", va="center", fontsize=8, color=MUTED)
        if key == "tools_under_50":
            ax.axvline(100 * MARGIN, color=MUTED, linestyle=(0, (4, 3)), linewidth=1)
            ax.text(100 * MARGIN + 1, -0.55, "12% margin", fontsize=7.5, color=MUTED, ha="left", va="center")
        ax.set_title(title, fontsize=10, color=INK, loc="left")
        ax.set_xlim(-2, 100)
        ax.set_ylim(-0.9, len(TOOLS) - 0.5)
    axes[0].set_yticks(range(len(TOOLS)))
    axes[0].set_yticklabels(TOOLS[::-1])
    fig.supxlabel("People with the multiregional pattern (%, exact 95% CI)", fontsize=8.5, color=INK)
    fig.tight_layout()
    for ext in ("png", "pdf"):
        fig.savefig(out / f"figure_tools.{ext}", dpi=300)
    plt.close(fig)


def cohorts_figure(r, out):
    items = [(c, v) for c, v in r["primary_by_cohort"].items() if v["n"]]
    items.append(("All under 50 (primary)", r["primary"]))
    fig, ax = plt.subplots(figsize=(6.0, 0.45 * len(items) + 1.0))
    style(ax)
    for i, (c, v) in enumerate(items):
        y = len(items) - 1 - i
        bold = c.startswith("All")
        ax.plot([100 * v["low"], 100 * v["high"]], [y, y], color=COLOUR["FLAMeS"], linewidth=2.6 if bold else 2)
        ax.plot(100 * v["p"], y, "D" if bold else "o", color=COLOUR["FLAMeS"], markersize=7, markeredgecolor="white")
        ax.text(100 * v["high"] + 1.5, y, f"{v['x']}/{v['n']}", va="center", fontsize=8, color=MUTED)
    ax.axvline(100 * MARGIN, color=MUTED, linestyle=(0, (4, 3)), linewidth=1)
    ax.set_yticks(range(len(items)))
    ax.set_yticklabels([c for c, _ in items][::-1])
    ax.set_xlim(-2, 100)
    ax.set_xlabel("FLAMeS: people with the multiregional pattern (%, exact 95% CI)", fontsize=8.5, color=INK)
    fig.tight_layout()
    for ext in ("png", "pdf"):
        fig.savefig(out / f"figure_cohorts.{ext}", dpi=300)
    plt.close(fig)


def main(results, out):
    r = json.load(open(results, encoding="utf-8"))
    out = Path(out)
    out.mkdir(parents=True, exist_ok=True)
    tools_table(r, out)
    cohorts_table(r, out)
    agreement_table(r, out)
    tools_figure(r, out)
    cohorts_figure(r, out)


if __name__ == "__main__":
    main(sys.argv[1], sys.argv[2])
