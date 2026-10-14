"""
Fit Signal analysis pipeline.

Reads the pulled review data plus the committed fit labels and reproduces
data/results_final.json: the flagship fit calibration, the body-type breakdown,
the size recommender grid, the AI-vs-ground-truth validation, and the
cross-brand comparison.

    python src/pipeline.py

Inputs  (data/):
    flagship_structured.json  - 1,500 date-sorted flagship reviews w/ structured fields
    classify_source.json      - the text samples that were classified (with structured fit)
    {flagship,relwen,barbour}_llm_labels.tsv - recorded LLM fit labels (see classify.py)

Output  (data/):
    results_final.json
"""
import json, re, math
from collections import Counter, defaultdict

DATA = "data"
ORDER = ["XS", "S", "M", "L", "XL", "XXL", "3XL"]


# ---------- parsing (self-reported fields, lightly cleaned) ----------
def parse_height(h):
    if not h:
        return None
    m = re.search(r"(\d)\s*[’'′]\s*(\d{1,2})", str(h))
    if m:
        return int(m.group(1)) * 12 + int(m.group(2))
    m = re.search(r"(\d)\s*[’'′]", str(h))
    return int(m.group(1)) * 12 if m else None


def parse_weight(w):
    if w is None:
        return None
    m = re.search(r"(\d{2,3})", str(w))
    if not m:
        return None
    v = int(m.group(1))
    return v if 90 <= v <= 400 else None


SIZEMAP = {"xs": "XS", "s": "S", "small": "S", "m": "M", "medium": "M",
           "l": "L", "large": "L", "xl": "XL", "xxl": "XXL", "2xl": "XXL",
           "2x": "XXL", "xxxl": "3XL", "3xl": "3XL", "3x": "3XL"}


def parse_size(s):
    if not s:
        return None
    return SIZEMAP.get(str(s).strip().lower().replace(" ", ""))


def parse_body(b):
    if not b:
        return None
    b = str(b).strip()
    return None if "rock" in b.lower() else b


def hband(h):
    return ("≤5ft6" if h <= 67 else "5ft7-8" if h <= 69 else "5ft9-10"
            if h <= 71 else "5ft11-6ft0" if h <= 73 else "6ft1+")


def wband(w):
    lo = (w // 20) * 20
    return f"{lo}-{lo + 19}"


def wilson(k, n, z=1.96):
    if not n:
        return [None, None]
    p = k / n
    d = 1 + z * z / n
    c = (p + z * z / (2 * n)) / d
    h = z * math.sqrt(p * (1 - p) / n + z * z / (4 * n * n)) / d
    return [round(100 * (c - h), 1), round(100 * (c + h), 1)]


# ---------- flagship structured analysis ----------
def flagship_analysis():
    rows = json.load(open(f"{DATA}/flagship_structured.json"))
    clean = [dict(score=r["s"], fit=r["f"], h=parse_height(r["h"]),
                  w=parse_weight(r["w"]), size=parse_size(r["sk"]),
                  bt=parse_body(r["bt"])) for r in rows]

    fit = [c["fit"] for c in clean if c["fit"] in (1, 2, 3)]
    n = len(fit)
    c = Counter(fit)
    small, true, large = c[1], c[2], c[3]
    p_s, p_l = small / n, large / n
    se = math.sqrt((p_s * (1 - p_s) + p_l * (1 - p_l) + 2 * p_s * p_l) / n)
    net = (small - large) / n
    calib = dict(n=n, small=small, true=true, large=large,
                 pct_small=round(100 * small / n, 1), pct_true=round(100 * true / n, 1),
                 pct_large=round(100 * large / n, 1), net_runs_small=round(100 * net, 1),
                 net_ci95=[round(100 * (net - 1.96 * se), 1), round(100 * (net + 1.96 * se), 1)])

    by_bt = {}
    for bt in ["Slim", "Athletic", "Average", "Heavy Set"]:
        sub = [x["fit"] for x in clean if x["bt"] == bt and x["fit"] in (1, 2, 3)]
        if len(sub) >= 20:
            cc, nn = Counter(sub), len(sub)
            by_bt[bt] = dict(n=nn, pct_small=round(100 * cc[1] / nn, 1),
                             pct_true=round(100 * cc[2] / nn, 1),
                             pct_large=round(100 * cc[3] / nn, 1),
                             net_runs_small=round(100 * (cc[1] - cc[3]) / nn, 1))

    pts = [x for x in clean if x["h"] and x["w"] and x["size"]]
    grid = defaultdict(list)
    for x in pts:
        grid[(hband(x["h"]), wband(x["w"]))].append(x["size"])
    size_grid = {}
    for (hb, wb), sizes in grid.items():
        if len(sizes) >= 5:
            cc = Counter(sizes)
            modal, mc = cc.most_common(1)[0]
            size_grid[f"{hb}|{wb}"] = dict(h=hb, w=wb, n=len(sizes), modal=modal,
                                           conf=round(mc / len(sizes), 2),
                                           dist={k: cc[k] for k in ORDER if cc[k]})

    coverage = dict(total=len(rows), with_fit=n,
                    with_height=sum(1 for x in clean if x["h"]),
                    with_weight=sum(1 for x in clean if x["w"]),
                    with_size=sum(1 for x in clean if x["size"]),
                    with_hw_size=len(pts))
    return calib, by_bt, size_grid, coverage


# ---------- validation + cross-brand (from recorded LLM labels) ----------
def load_labels(path):
    d = {}
    for line in open(path):
        line = line.strip()
        if line:
            i, l = line.split("\t")
            d[int(i)] = l
    return [d[i] for i in range(len(d))]


def validate_and_crossbrand(calib):
    src = json.load(open(f"{DATA}/classify_source.json"))
    labels = load_labels(f"{DATA}/flagship_llm_labels.tsv")
    truth = [{1: "small", 2: "true", 3: "large"}[r["f"]] for r in src["flagship"]]
    pairs = list(zip(labels, truth))
    signal = [(p, t) for p, t in pairs if p != "none"]
    acc_signal = sum(p == t for p, t in signal) / len(signal)
    n_abstain = sum(1 for p in labels if p == "none")
    # if a review with no fit cue is treated as true-to-size, overall accuracy:
    acc_default = sum((("true" if p == "none" else p) == t) for p, t in pairs) / len(pairs)
    validation = dict(n=len(labels), abstain_rate=round(n_abstain / len(labels), 3),
                      n_signal=len(signal), acc_signal=round(acc_signal, 3),
                      acc_default_true=round(acc_default, 3),
                      missed_in_abstain=sum(1 for p, t in pairs if p == "none" and t != "true"),
                      n_abstain=n_abstain)

    def brand(labels, structured=None):
        s, l = labels.count("small"), labels.count("large")
        d = s + l
        out = dict(n_reviews=len(labels), directional=d,
                   mention_rate=round(100 * d / len(labels), 1),
                   pct_small_of_directional=round(100 * s / d, 1) if d else None,
                   net_runs_small=round(100 * (s - l) / d, 1) if d else None,
                   ci_small=wilson(s, d))
        if structured:
            out.update(structured)
        return out

    s, l = calib["small"], calib["large"]
    dirn = s + l
    ft_struct = dict(structured_net=round(100 * (s - l) / dirn, 1),
                     structured_pct_small_of_dir=round(100 * s / dirn, 1),
                     structured_n=dirn, structured_ci=wilson(s, dirn))
    cb = {
        "Flint & Tinder": brand(labels, ft_struct),
        "Relwen": brand(load_labels(f"{DATA}/relwen_llm_labels.tsv")),
        "Barbour": brand(load_labels(f"{DATA}/barbour_llm_labels.tsv")),
    }
    return validation, cb


def main():
    calib, by_bt, size_grid, coverage = flagship_analysis()
    validation, cb = validate_and_crossbrand(calib)
    final = dict(
        meta=dict(category="Jackets", brands=list(cb), pulled_at="2026-10-13",
                  flagship="Flint & Tinder Flannel-Lined Waxed Trucker Jacket"),
        flagship=dict(calibration=calib, by_body_type=by_bt, coverage=coverage,
                      size_grid=size_grid),
        crossbrand=cb, validation=validation)
    json.dump(final, open(f"{DATA}/results_final.json", "w"), indent=2)
    print("wrote data/results_final.json")
    print(f"  flagship net runs-small: {calib['net_runs_small']}% "
          f"(CI {calib['net_ci95']}, n={calib['n']})")
    print(f"  heavy-set {by_bt['Heavy Set']['pct_small']}% small vs "
          f"slim {by_bt['Slim']['pct_small']}%")
    print(f"  validation: {int(validation['acc_signal']*100)}% accurate where text "
          f"mentions fit; {int(validation['abstain_rate']*100)}% of reviews give no cue")
    for b, v in cb.items():
        print(f"  {b}: {v['pct_small_of_directional']}% of fit mentions say small (n={v['directional']})")


if __name__ == "__main__":
    main()
