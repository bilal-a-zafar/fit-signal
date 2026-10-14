"""
Extract a fit-direction label from review TEXT using an LLM.

This is the step validated in pipeline.py: the model reads only the review text
(never the structured Fit field) and labels each review small / true / large /
none, where "none" means the text carries no fit cue. On the flagship, those
labels are then scored against the structured Fit field as ground truth.

The committed data/*_llm_labels.tsv files are the recorded output of this script.
Re-running it needs an Anthropic API key:

    pip install anthropic
    export ANTHROPIC_API_KEY=sk-ant-...
    python src/classify.py flagship   # or relwen / barbour

Labels are deterministic-ish at temperature 0 but may shift slightly between
model versions; the committed labels are the run behind the published figures.
"""
import json, os, sys

PROMPT = """You are labeling how a jacket fits from a customer review.

Read ONLY the review text. Decide how the jacket runs for this reviewer:
- "small"  : runs small / tight / snug, advises sizing up, "had to size up",
             a normal size that was too small, or a clearly slim-and-restrictive cut.
- "large"  : runs large / boxy / roomy, advises sizing down, "sized down",
             a normal size that was too big.
- "true"   : fits as expected / true to size / "fits perfectly" with no size problem.
- "none"   : the review says nothing about how it fits (e.g. only color, warmth,
             shipping, or "great jacket").

Judge girth/overall size, not sleeve length alone. Do not infer a size problem
from praise. Return one label per review.

Return a JSON array of objects: [{"i": <index>, "label": "<small|true|large|none>"}].
Reviews:
"""


def classify(brand):
    import anthropic
    src = json.load(open("data/classify_source.json"))[brand]
    # cap to the samples used in the study
    cap = {"flagship": 120, "relwen": 100, "barbour": 95}[brand]
    src = [r for r in src if (brand != "flagship" or r.get("f") in (1, 2, 3))][:cap]

    lines = [f'{i}. TITLE: {r.get("t","")} :: {r.get("c","")[:400]}'
             for i, r in enumerate(src)]
    client = anthropic.Anthropic()
    msg = client.messages.create(
        model="claude-opus-4-20250514",
        max_tokens=4000, temperature=0,
        messages=[{"role": "user", "content": PROMPT + "\n".join(lines)}],
    )
    text = msg.content[0].text
    start, end = text.find("["), text.rfind("]") + 1
    labels = {o["i"]: o["label"] for o in json.loads(text[start:end])}
    out = f"data/{brand}_llm_labels.tsv"
    with open(out, "w") as f:
        for i in range(len(src)):
            f.write(f"{i}\t{labels.get(i, 'none')}\n")
    print(f"{len(src)} labels -> {out}", file=sys.stderr)


if __name__ == "__main__":
    brand = sys.argv[1] if len(sys.argv) > 1 else "flagship"
    if not os.environ.get("ANTHROPIC_API_KEY"):
        sys.exit("set ANTHROPIC_API_KEY to re-run classification "
                 "(committed data/*_llm_labels.tsv are the recorded output)")
    classify(brand)
