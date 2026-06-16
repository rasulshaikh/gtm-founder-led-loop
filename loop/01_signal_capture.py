#!/usr/bin/env python3
"""
Phase 01: Signal Capture
Ingests LinkedIn engagers (from PhantomBuster, HeyReach, or manual export),
enriches with company/role data, and outputs a clean engager file.

Input sources supported:
  - LinkedIn post engager CSV (PhantomBuster "Post Likers/Commenters" export)
  - Manual CSV with: name, linkedin_url, company, title, post_url, engagement_type

Usage:
    python loop/01_signal_capture.py --input raw_engagers.csv --output enriched.csv
    python loop/01_signal_capture.py --post-url "linkedin.com/posts/..." --output enriched.csv
"""

import argparse
import csv
import json
import os
import sys
import time
from datetime import date
from pathlib import Path
from typing import Optional
import requests


APOLLO_API_URL = "https://api.apollo.io/v1/people/match"
ENGAGEMENT_WEIGHTS = {
    "comment": 10,
    "like": 4,
    "share": 8,
    "repost": 7,
    "dm": 15,
    "profile_view": 5,
    "connection_request": 12,
}

OUTPUT_FIELDS = [
    "full_name", "first_name", "company", "title", "linkedin_url",
    "email", "industry", "employees", "website",
    "engagement_type", "engagement_score", "post_url", "post_topic",
    "enriched_at",
]


def parse_engagement_score(engagement_type: str) -> int:
    """Score the engagement type by warmth."""
    score = 0
    for key, weight in ENGAGEMENT_WEIGHTS.items():
        if key in engagement_type.lower():
            score += weight
    return score or ENGAGEMENT_WEIGHTS["like"]


def enrich_with_apollo(
    full_name: str,
    company: str,
    linkedin_url: str,
    api_key: str,
) -> dict:
    """Enrich a contact via Apollo People Match API."""
    payload = {
        "api_key": api_key,
        "name": full_name,
        "organization_name": company,
        "linkedin_url": linkedin_url,
    }
    try:
        resp = requests.post(APOLLO_API_URL, json=payload, timeout=15)
        if resp.status_code == 200:
            person = resp.json().get("person") or {}
            org = person.get("organization") or {}
            return {
                "email": person.get("email", ""),
                "title": person.get("title", ""),
                "industry": org.get("industry", ""),
                "employees": str(org.get("estimated_num_employees", "")),
                "website": org.get("website_url", ""),
            }
    except Exception:
        pass
    return {}


def normalize_row(row: dict) -> dict:
    """Normalize column names from different export formats."""
    name = (
        row.get("full_name")
        or row.get("fullName")
        or row.get("name")
        or f"{row.get('firstName', '')} {row.get('lastName', '')}".strip()
    )
    first = name.split()[0] if name else ""
    return {
        "full_name": name,
        "first_name": first,
        "company": row.get("company") or row.get("companyName") or row.get("organization") or "",
        "title": row.get("title") or row.get("jobTitle") or row.get("headline") or "",
        "linkedin_url": row.get("linkedin_url") or row.get("linkedinUrl") or row.get("profileUrl") or "",
        "email": row.get("email") or "",
        "industry": row.get("industry") or "",
        "employees": row.get("employees") or row.get("companySize") or "",
        "website": row.get("website") or row.get("companyWebsite") or "",
        "engagement_type": row.get("engagement_type") or row.get("action") or "like",
        "post_url": row.get("post_url") or row.get("postUrl") or "",
        "post_topic": row.get("post_topic") or row.get("postTopic") or "",
    }


def capture(
    input_csv: str,
    output_csv: str,
    post_topic: str = "",
    enrich: bool = True,
    delay: float = 0.5,
) -> None:
    """Main capture pipeline."""
    apollo_key = os.environ.get("APOLLO_API_KEY", "")
    if enrich and not apollo_key:
        print("Warning: APOLLO_API_KEY not set — skipping enrichment.")
        enrich = False

    with open(input_csv, newline="", encoding="utf-8") as f:
        rows = list(csv.DictReader(f))

    print(f"Processing {len(rows)} engagers from {input_csv}...")

    results = []
    for i, raw_row in enumerate(rows, 1):
        row = normalize_row(raw_row)

        if post_topic:
            row["post_topic"] = post_topic

        row["engagement_score"] = parse_engagement_score(row["engagement_type"])

        if enrich and (not row["email"] or not row["industry"]):
            enriched = enrich_with_apollo(
                full_name=row["full_name"],
                company=row["company"],
                linkedin_url=row["linkedin_url"],
                api_key=apollo_key,
            )
            row.update({k: v for k, v in enriched.items() if v and not row.get(k)})
            if i < len(rows):
                time.sleep(delay)

        row["enriched_at"] = str(date.today())
        print(f"  [{i}/{len(rows)}] {row['full_name']} @ {row['company']} — {row['engagement_type']} (score: {row['engagement_score']})")
        results.append(row)

    results.sort(key=lambda r: int(r.get("engagement_score") or 0), reverse=True)

    with open(output_csv, "w", newline="", encoding="utf-8") as f:
        writer = csv.DictWriter(f, fieldnames=OUTPUT_FIELDS, extrasaction="ignore")
        writer.writeheader()
        writer.writerows(results)

    print(f"\nDone. {len(results)} engagers captured → {output_csv}")
    comments = sum(1 for r in results if "comment" in r.get("engagement_type", "").lower())
    likes = sum(1 for r in results if r.get("engagement_type", "").lower() == "like")
    print(f"Comments: {comments}  Likes: {likes}  Other: {len(results) - comments - likes}")


def main() -> None:
    parser = argparse.ArgumentParser(description="Phase 01: Signal Capture — ingest and enrich LinkedIn engagers")
    parser.add_argument("--input", required=True, help="Input CSV from PhantomBuster or manual export")
    parser.add_argument("--output", default="enriched_engagers.csv")
    parser.add_argument("--post-topic", default="", help="What the post was about (used in outbound context)")
    parser.add_argument("--no-enrich", action="store_true", help="Skip Apollo enrichment")
    parser.add_argument("--delay", type=float, default=0.5)
    args = parser.parse_args()

    capture(
        input_csv=args.input,
        output_csv=args.output,
        post_topic=args.post_topic,
        enrich=not args.no_enrich,
        delay=args.delay,
    )


if __name__ == "__main__":
    main()
