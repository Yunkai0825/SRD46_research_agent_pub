"""Display missing numerical solutions without interpolating across them."""


def shade_unconverged(ax, curve):
    """Shade failed samples to their neighbouring sample midpoints."""
    x = list(curve.pH_values)
    failed = [not getattr(result, "converged", True)
              for result in curve.results]
    spans = []
    i = 0
    while i < len(x):
        if not failed[i]:
            i += 1
            continue
        start = i
        while i + 1 < len(x) and failed[i + 1]:
            i += 1
        left = x[start] if start == 0 else (x[start - 1] + x[start]) / 2
        right = x[i] if i == len(x) - 1 else (x[i] + x[i + 1]) / 2
        spans.append(ax.axvspan(
            min(left, right), max(left, right), color="0.7", alpha=0.4,
            linewidth=0, zorder=0,
            label="Unconverged" if not spans else "_nolegend_",
        ))
        i += 1
    return spans
