"""
Turn data/results_final.json into site/fitdata.js, the data the page reads.

    python src/build_site_data.py
"""
import json

r = json.load(open("data/results_final.json"))
grid = r["flagship"]["size_grid"]

HB = ["≤5ft6", "5ft7-8", "5ft9-10", "5ft11-6ft0", "6ft1+"]
HLAB = {"≤5ft6": "5’6″ or under", "5ft7-8": "5’7″–5’8″",
        "5ft9-10": "5’9″–5’10″", "5ft11-6ft0": "5’11″–6’0″",
        "6ft1+": "6’1″ and up"}
WB = sorted({v["w"] for v in grid.values()}, key=lambda w: int(w.split("-")[0]))


def wlab(w):
    lo = int(w.split("-")[0])
    return f"{lo}–{lo + 19} lb"


cells = {v["h"] + "|" + v["w"]: {"modal": v["modal"], "n": v["n"],
                                 "conf": v["conf"], "dist": v["dist"]}
         for v in grid.values()}

data = {"meta": r["meta"], "calib": r["flagship"]["calibration"],
        "coverage": r["flagship"]["coverage"], "body": r["flagship"]["by_body_type"],
        "validation": r["validation"], "crossbrand": r["crossbrand"],
        "rec": {"hbands": HB, "hlab": HLAB, "wbands": WB,
                "wlab": {w: wlab(w) for w in WB}, "cells": cells}}

open("site/fitdata.js", "w").write(
    "window.FITDATA=" + json.dumps(data, ensure_ascii=False, separators=(",", ":")) + ";")
print("wrote site/fitdata.js")
