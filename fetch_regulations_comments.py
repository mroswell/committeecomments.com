import requests
import pandas as pd
from datetime import datetime, timedelta
from tqdm import tqdm
import time

import os

# Constants
DOCKET_ID = "CDC-2026-0199"
# "FDA-2025-N-1146"
BASE_URL = "https://api.regulations.gov/v4"
# REGULATIONS_API_KEY = "DEMO_KEY"  # Replace with your actual API key
REGULATIONS_API_KEY = os.environ.get("REGULATIONS_API_KEY", "DEMO_KEY")

HEADERS = {"Accept": "application/json", "X-Api-Key": REGULATIONS_API_KEY}

def get_documents(docket_id):
    url = f"{BASE_URL}/documents"
    params = {"filter[docketId]": docket_id, "page[size]": 250}
    docs = []
    page = 1
    while True:
        params["page[number]"] = page
        resp = requests.get(url, headers=HEADERS, params=params)
        data = resp.json()
        docs.extend(data.get("data", []))
        if "next" not in data.get("links", {}):
            break
        page += 1
    return docs

def get_comments_for_document(object_id):
    url = f"{BASE_URL}/comments"
    comments = []
    page_size = 250 # Use max allowed by API for efficiency
    page = 1
    while True:
        print(f"Fetching comments for document {object_id}, page {page}")
        params = {
            "filter[commentOnId]": object_id,
            "page[size]": page_size,
            "page[number]": page,
            "sort": "lastModifiedDate,documentId"
        }
        try:
            resp = requests.get(url, headers=HEADERS, params=params)
            data = resp.json()
            comments_batch = data.get("data", [])
            if not comments_batch:
                break
            comments.extend(comments_batch)
            page += 1
            time.sleep(0.2)  # Optional: be nice to the API
        except requests.exceptions.RequestException as e:
            print(f"Error fetching comments for document {object_id}: {e}")
            break
    return comments

def get_comment_details(comment_id):
    url = f"{BASE_URL}/comments/{comment_id}"   #Next Time start from here : FDA-2025-N-1146-0965
    params = {}
    resp = requests.get(url, headers=HEADERS, params=params)
    if resp.status_code == 200:
        return resp.json().get("data", {})
    else:
        print(f"Failed to fetch details for comment {comment_id}")
        return {}

if __name__ == "__main__":
    documents = get_documents(DOCKET_ID)
    print(f"Found {len(documents)} documents for docket {DOCKET_ID}")
    all_comments = []
    for doc in tqdm(documents, desc="Documents"):
        object_id = doc["attributes"]["objectId"]
        comments = get_comments_for_document(object_id)
        print(f"Document {object_id}: {len(comments)} comments")
        all_comments.extend(comments)
    print(f"Total comments fetched: {len(all_comments)}")

    # Save to CSV
    if all_comments:
        detailed_comments = []
        try:
            for c in tqdm(all_comments, desc="Fetching comment details"):
                comment_id = c.get("id")
                detail = get_comment_details(comment_id)
                attributes = detail.get("attributes", {})
                detailed_comments.append({
                    "Comment ID": comment_id,
                    "Tracking Number": attributes.get("trackingNbr"),
                    "Country": attributes.get("country"),
                    "State or Province": attributes.get("stateProvinceRegion"),
                    "Document Subtype": attributes.get("subtype"),
                    "Received Date": attributes.get("receiveDate"),
                    "Comment": attributes.get("comment"),
                    "URL": detail.get("links", {}).get("self"),
                })
        except Exception as e:
            print(f"Exception occurred: {e}")
            print("Writing buffered comments to CSV before exiting...")

        # Always write whatever is in the buffer
        if detailed_comments:
            df = pd.DataFrame(detailed_comments)
            df.to_csv("detailed_comments.csv", index=False)
            print("Detailed comments saved to detailed_comments.csv")
        else:
            print("No detailed comments to save.")
    else:
        print("No comments to save.")
