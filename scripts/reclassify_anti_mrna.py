import os
import json
import time
import pandas as pd
import anthropic
from dotenv import load_dotenv
from tqdm import tqdm

load_dotenv()

# ── Settings ──────────────────────────────────────────────────────────────────
REPO_ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
CSV_PATH = os.path.join(REPO_ROOT, "data", "csv", "comments_CDC-2026-0199.csv")
SAVE_EVERY = 20
SLEEP_SECS = 3
MODEL = "claude-sonnet-4-20250514"
# ──────────────────────────────────────────────────────────────────────────────

client = anthropic.Anthropic(api_key=os.environ.get("ANTHROPIC_API_KEY"))


def build_prompt(comment_text):
    return f"""You are analyzing a public comment submitted to a federal advisory committee
docket on regulations.gov related to ACIP and VRBPAC.

This comment was previously classified as "anti-vaccine". Your job is to determine
whether the commenter is opposed to ALL vaccines broadly, or specifically opposed
to mRNA/COVID vaccines only.

Return exactly one of these two values (no quotes, no explanation):
anti-vaccine
anti-mRNA-vaccine

Guidance:
- "anti-mRNA-vaccine" — the commenter specifically opposes mRNA vaccines, COVID vaccines,
  or COVID shots, but does NOT express opposition to all vaccines broadly. They may even
  support other vaccines.
- "anti-vaccine" — the commenter is clearly and broadly opposed to vaccines in general,
  or opposes multiple vaccine types beyond just mRNA/COVID.
- If unclear or the comment opposes both mRNA and other vaccines, keep as "anti-vaccine".
- Vaccine injury is a legitimate concern, not misinformation.

Comment:
{comment_text}"""


def classify(comment_text, max_retries=5):
    if not comment_text or pd.isna(comment_text):
        return "anti-vaccine"
    for attempt in range(max_retries):
        try:
            message = client.messages.create(
                model=MODEL,
                max_tokens=50,
                messages=[{"role": "user", "content": build_prompt(comment_text)}]
            )
            result = message.content[0].text.strip()
            if result in ("anti-vaccine", "anti-mRNA-vaccine"):
                return result
            return "anti-vaccine"
        except (anthropic.APIConnectionError, anthropic.RateLimitError) as e:
            wait = 30 * (attempt + 1)
            print(f"\n  {type(e).__name__}: waiting {wait}s (attempt {attempt+1}/{max_retries})")
            time.sleep(wait)
        except Exception as e:
            print(f"\n  Error: {e}")
            return "anti-vaccine"
    print(f"\n  Gave up after {max_retries} retries")
    return "anti-vaccine"


if __name__ == "__main__":
    print(f"\n{'='*60}")
    print(f"Input:      {CSV_PATH}")
    print(f"Model:      {MODEL}")
    print(f"Task:       Reclassify anti-vaccine → anti-mRNA-vaccine where appropriate")
    print(f"{'='*60}\n")

    df = pd.read_csv(CSV_PATH)

    anti_vax = df[df["perspective"] == "anti-vaccine"]
    print(f"Total rows:           {len(df)}")
    print(f"Anti-vaccine rows:    {len(anti_vax)}")

    if len(anti_vax) == 0:
        print("No anti-vaccine rows to process!")
        exit()

    processed = 0
    reclassified = 0

    try:
        for idx in tqdm(anti_vax.index, desc="Reclassifying", unit="comment"):
            comment_text = df.at[idx, "comment"]
            result = classify(comment_text)

            if result == "anti-mRNA-vaccine":
                df.at[idx, "perspective"] = "anti-mRNA-vaccine"
                reclassified += 1

            processed += 1

            if processed % SAVE_EVERY == 0:
                df.to_csv(CSV_PATH, index=False)
                print(f"\n  Saved progress: {processed} checked, {reclassified} reclassified")

            time.sleep(SLEEP_SECS)

    except Exception as e:
        print(f"\nException occurred: {e}")
        print("Saving progress before exiting...")

    df.to_csv(CSV_PATH, index=False)
    print(f"\nDone!")
    print(f"  Checked:        {processed}")
    print(f"  Reclassified:   {reclassified}")
    print(f"  Still anti-vax: {processed - reclassified}")
    print(f"  Saved to:       {CSV_PATH}")
