# AKTION: Forest-Plots (Odds Ratios bzw. Average Marginal Effects) mit ggplot2. Eingabe: JSON {schluessel: {art, d: [[label, est, lo, hi, p], ...]}}
#   Rscript skripte/live_forest.R data/live/grafiken/forest/eingabe.json   # das Dashboard (skripte/live_dashboard.py) ruft es selbst auf
suppressPackageStartupMessages({library(ggplot2); library(jsonlite)})
a <- commandArgs(TRUE); ordner <- dirname(a[1])
PAL <- list(hell = list(text = "#2b2b28", text2 = "#5c5b55", gitter = "#d9d8d2", sig = "#d95926", ns = "#8a8981"),
            dunkel = list(text = "#ecebe4", text2 = "#b5b4aa", gitter = "#4a4a46", sig = "#f0703c", ns = "#9a998f"))
ein <- fromJSON(a[1], simplifyVector = FALSE)
forest <- function(e, p) {
  d <- data.frame(lab = vapply(e$d, \(x) x[[1]], ""), est = vapply(e$d, \(x) x[[2]], 0), lo = vapply(e$d, \(x) x[[3]], 0),
                  hi = vapply(e$d, \(x) x[[4]], 0), p = vapply(e$d, \(x) x[[5]], 0))
  d$lab <- factor(d$lab, levels = rev(unique(d$lab))); d$sig <- ifelse(d$p < .05, "sig", "ns")
  or <- e$art == "or"; null <- if (or) 1 else 0
  d$txt <- if (or) sprintf("%.2f [%.2f–%.2f]%s", d$est, d$lo, d$hi, ifelse(d$p < .05, " *", ""))
           else sprintf("%+.1f [%+.1f–%+.1f]%s", d$est, d$lo, d$hi, ifelse(d$p < .05, " *", ""))
  g <- ggplot(d, aes(est, lab, colour = sig)) + geom_vline(xintercept = null, colour = p$text2, linewidth = .4, linetype = 2) +
    geom_errorbarh(aes(xmin = lo, xmax = hi), height = 0, linewidth = .7) + geom_point(size = 2.6) +
    geom_text(aes(x = Inf, label = txt), hjust = 1.02, size = 3.1, colour = p$text, show.legend = FALSE) +
    scale_colour_manual(values = c(sig = p$sig, ns = p$ns)) + labs(x = if (or) "Odds ratio (log scale, 95 % CI)" else "Percentage points (95 % CI)", y = NULL)
  if (or) g <- g + scale_x_log10(breaks = c(.1, .25, .5, 1, 2, 4, 10), expand = expansion(mult = c(.05, .55))) else g <- g + scale_x_continuous(expand = expansion(mult = c(.05, .55)))
  g + theme_minimal(base_size = 11) + theme(text = element_text(colour = p$text), axis.text = element_text(colour = p$text2), axis.title.x = element_text(colour = p$text2, size = 9),
    panel.grid.minor = element_blank(), panel.grid.major.x = element_blank(), panel.grid.major.y = element_line(colour = p$gitter, linewidth = .3),
    legend.position = "none", plot.background = element_rect(fill = NA, colour = NA), panel.background = element_rect(fill = NA, colour = NA), plot.margin = margin(4, 6, 4, 4))
}
for (k in names(ein)) for (m in names(PAL)) {
  n <- length(ein[[k]]$d)
  tryCatch({ svg(file.path(ordner, sprintf("%s_%s.svg", k, m)), width = 8, height = .3 * n + 1, bg = "transparent"); print(forest(ein[[k]], PAL[[m]])); dev.off() },
           error = function(e) { while (dev.cur() > 1) dev.off(); unlink(file.path(ordner, sprintf("%s_%s.svg", k, m))); message(k, ": ", conditionMessage(e)) })
}
cat("Forest-Plots geschrieben\n")
