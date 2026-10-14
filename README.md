# Fit Signal

Reading how Huckberry's jackets actually fit, straight from the review data the
store already collects, with the one AI step in it checked against ground truth.

Built from public review data only. No internal Huckberry data was used.

## The question

A multi-brand retailer like Huckberry doesn't cut its own jackets, so sizing is
inconsistent from brand to brand and fit is a top driver of apparel returns. The
signal for "which jackets run small, and for whom" already exists, sitting in
thousands of reviews. Nobody reads all of them.

## What's here

Three things, built on Flint & Tinder, Relwen, and Barbour jackets:

1. **Fit calibration.** The flagship Flint & Tinder waxed trucker runs small
   (net +21pp, 95% CI 19–24, n=1,377 structured fit ratings). The useful part is
   that it's uneven by build: heavy-set reviewers call it small 41% of the time,
   slim reviewers 14%. A single "runs small" flag is too blunt.

2. **A size recommender.** Reviewers volunteer height, weight, and the size they
   kept. For any build, that's a direct answer to the sizing question from people
   who already made the call (1,119 height+weight+size records).

3. **A cross-brand read, with its AI step validated.** Only the flagship collects
   a structured fit rating. For Relwen and Barbour, fit is pulled from review text
   by an LLM. Before trusting that, it's scored where truth exists: on the flagship
   the model reads only the text, guesses the fit, and is checked against the
   structured rating it never saw.
   - 86.9% correct where the text actually mentions fit (n=61).
   - 49% of reviews carry no fit cue in the text at all.
   - The model's brand-level read of the flagship (83% net-small from text) lands
     on its structured truth (85%), which is what licenses using it on the other
     two brands.

Finding across brands (share of fit-mentioning reviews that say "runs small"):
Flint & Tinder ~92%, Relwen ~70% (thin, n=10), Barbour ~61% (contested, with real
clusters of both "slim/tight" and "boxy/sleeves long").

## Run it

```bash
pip install -r requirements.txt
python src/pipeline.py            # reproduces data/results_final.json + prints the headline numbers
python src/build_site_data.py     # writes site/fitdata.js
# open site/index.html in a browser for the interactive page
```

Re-pull the raw reviews (optional; the pulled data is committed):

```bash
python src/fetch_reviews.py P99266 --pages 10 --out data/flagship_raw.json
```

Re-run the text classification (optional; labels are committed). Needs an API key:

```bash
export ANTHROPIC_API_KEY=sk-ant-...
python src/classify.py flagship   # then relwen, barbour
```

## Layout

```
src/
  fetch_reviews.py     Yotpo widget API pull (public, no auth)
  classify.py          LLM fit extraction from review text (the step that gets validated)
  pipeline.py          calibration + body-type + size grid + validation + cross-brand
  build_site_data.py   results -> site/fitdata.js
data/
  flagship_structured.json   1,500 date-sorted flagship reviews w/ structured fields
  text_samples.json          text samples for classification
  *_llm_labels.tsv           recorded LLM fit labels (classify.py output)
  results_final.json         everything the page reads
site/
  index.html, fitdata.js     the interactive page
notebooks/
  walkthrough.ipynb          the analysis end to end
```

## How the data is pulled

Huckberry serves reviews through Yotpo. The widget API is public and returns JSON,
including each reviewer's structured fit/height/weight/size fields where the
product's form collects them. Yotpo's product id is `P` + the number in the
Huckberry product URL. Reviews are pulled sorted by date so the sample is
representative across star ratings rather than front-loading 5-star reviews.

## What this is and isn't

- Reviews come from people who kept the jacket. Returners, who matter most for
  fit, are mostly absent. This reads the fit of survivors.
- The brand comparison is anchored by one richly-measured flagship and two thin
  text samples. It's a direction to check, not a verdict to ship.
- The real outcome is returns, which live in Huckberry's systems. Pointed at return
  and exchange data, the "runs small" signal becomes a dollar figure instead of an
  inference.
- Height and weight are self-reported and lightly cleaned.

---

Bilal Zafar. Analysis in Python; fit extraction and validation with Claude.
