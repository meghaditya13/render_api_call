import re
import httpx
import os
from bs4 import BeautifulSoup

API_KEY = os.getenv("GEMINI_API_KEY")
API_URL = "https://generativelanguage.googleapis.com/v1beta/models/gemini-2.5-flash:generateContent"

async def fetch_html(url):
    async with httpx.AsyncClient() as client:
        response = await client.get(url)
        response.raise_for_status()
        return response.text

def remove_irrelevant_sections(text):
    sections_to_remove = [
        r"introduction[\s\S]+?(?=\n[a-zA-Z ]{3,}:|\n\n)",
        r"definitions[\s\S]+?(?=\n[a-zA-Z ]{3,}:|\n\n)",
        r"changes (to|in) .*?policy[\s\S]+?(?=\n[a-zA-Z ]{3,}:|\n\n)",
        r"contact (us|information)[\s\S]+?(?=\n[a-zA-Z ]{3,}:|\n\n)",
        r"governing law[\s\S]+?(?=\n[a-zA-Z ]{3,}:|\n\n)",
        r"effective date[\s\S]+?(?=\n[a-zA-Z ]{3,}:|\n\n)",
        r"data (controller|processor)[\s\S]+?(?=\n[a-zA-Z ]{3,}:|\n\n)"
    ]
    for pattern in sections_to_remove:
        text = re.sub(pattern, "", text, flags=re.IGNORECASE)
    return text.strip()

def clean_html(html):
    soup = BeautifulSoup(html, "html.parser")
    for tag in soup(["script", "style", "noscript", "nav", "header", "footer", "aside"]):
        tag.extract()
    for hidden in soup.select('[style*="display:none"], [aria-hidden="true"]'):
        hidden.extract()
    text = soup.get_text(separator="\n")
    text = re.sub(r"\s+\n", "\n", text)
    text = re.sub(r"\n{2,}", "\n\n", text)
    text = re.sub(r"\s{2,}", " ", text)
    return remove_irrelevant_sections(text.strip())

async def summarize_policy(url):
    html = await fetch_html(url)
    cleaned_text = clean_html(html)

    if len(cleaned_text.split()) > 7000:
        raise ValueError("Privacy policy is too long to summarize.")

    payload = {
    "contents": [{ "parts": [{ "text": "Analyze the given privacy policy and return structured JSON following the schema exactly with values extracted from privacy policy.\n\n{cleaned_text}" }] }],
    "generationConfig": {
        "responseMimeType": "application/json",
        "responseSchema": {
            "type": "OBJECT",
            "properties": {
                "site": { "type": "STRING" },
                "policy_url": { "type": "STRING" },
                "last_updated": { "type": "STRING" },
                "summary": {
                    "type": "OBJECT",
                    "properties": {
                        "data": {
                            "type": "OBJECT",
                            "properties": {
                                "can_company_collect_data": { "type": "STRING" },
                                "is_company_collecting_data": { "type": "STRING" },
                                "data_collected": {
                                    "type": "ARRAY",
                                    "items": { "type": "STRING" }
                                },
                                "data_usage": {
                                    "type": "ARRAY",
                                    "items": { "type": "STRING" }
                                }
                            },
                            "propertyOrdering": ["can_company_collect_data", "is_company_collecting_data", "data_collected", "data_usage"]
                        },
                        "data_sharing": {
                            "type": "OBJECT",
                            "properties": {
                                "do_they_share": { "type": "BOOLEAN" },
                                "whom_can they_share": {
                                    "type": "ARRAY",
                                    "items": { "type": "STRING" }
                                },
                                "whom_are_they_sharing": {
                                    "type": "ARRAY",
                                    "items": { "type": "STRING" }
                                },
                                "what_do_they_share": {
                                    "type": "ARRAY",
                                    "items": { "type": "STRING" }
                                }
                            },
                            "propertyOrdering": ["do_they_share", "whom_can they_share", "whom_are_they_sharing", "what_do_they_share"]
                        },
                        "can_delete_account": { "type": "BOOLEAN" },
                        "camera_mic_location_access": {
                            "type": "OBJECT",
                            "properties": {
                                "camera": { "type": "BOOLEAN" },
                                "microphone": { "type": "BOOLEAN" },
                                "location": { "type": "BOOLEAN" }
                            },
                            "propertyOrdering": ["camera", "microphone", "location"]
                        },
                        "uses_targeted_ads": { "type": "BOOLEAN" },
                        "consent_required": { "type": "BOOLEAN" },
                        "opt_out_options": { "type": "STRING" },
                        "collects_children_data": { "type": "BOOLEAN" },
                        "gdpr_rights": { "type": "BOOLEAN" }
                    },
                    "propertyOrdering": ["data", "data_sharing", "can_delete_account", "camera_mic_location_access", "uses_targeted_ads", "consent_required", "opt_out_options", "collects_children_data", "gdpr_rights"]
                },
                "display": {
                    "type": "OBJECT",
                    "properties": {
                        "summary_text": { "type": "STRING" },
                        "risk_level": { "type": "STRING" },
                        "recommendation": { "type": "STRING" }
                    },
                    "propertyOrdering": ["summary_text", "risk_level", "recommendation"]
                }
            },
            "propertyOrdering": ["site", "policy_url", "last_updated", "summary", "display"]
        }
    }
    }

    headers = {
        "Content-Type": "application/json",
        "x-goog-api-key": API_KEY
    }

    async with httpx.AsyncClient() as client:
        response = await client.post(API_URL, headers=headers, json=payload)
        response.raise_for_status()
        return response.json()["candidates"][0]["content"]["parts"][0]["text"]
