#!/usr/bin/env python3
# Wandelt den Regelgraphen von Snakemake (dot) in ein Mermaid-Diagramm um, das GitHub direkt darstellt (kein Graphviz nötig).
#   snakemake -s workflow/Snakefile --rulegraph | python3 workflow/rulegraph_zu_mermaid.py
import re, sys

dot = sys.stdin.read()
knoten = {m.group(1): m.group(2) for m in re.finditer(r'^\s*(\d+)\[label = "([^"]+)"', dot, re.M)}
kanten = re.findall(r'^\s*(\d+) -> (\d+)', dot, re.M)
# Die Sammelregel "alle" hat Kanten von jeder Stufe und verdeckt den eigentlichen Ablauf: weglassen
alle = {k for k, n in knoten.items() if n == "alle"}
knoten = {k: n for k, n in knoten.items() if k not in alle}
kanten = [(a, b) for a, b in kanten if a not in alle and b not in alle]
print("```mermaid\nflowchart LR")
for k, name in knoten.items():
    print(f'    n{k}["{name}"]')
for a, b in kanten:
    print(f"    n{a} --> n{b}")
print("```")
