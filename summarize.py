import re
import httpx
import os
from bs4 import BeautifulSoup
from urllib.parse import urlparse, urljoin
import requests
#import trafilatura

API_KEY = os.getenv("GEMINI_API_KEY")
API_URL = "https://generativelanguage.googleapis.com/v1beta/models/gemini-2.5-flash:generateContent"
S_API_KEY = os.getenv("S_API_KEY")

COMMON_PRIVACY_PATHS = [
    "/privacy-policy", "/legal/privacy-policy", "/legal/privacy", "/privacy"
]

async def fetch_html(url):
    async with httpx.AsyncClient() as client:
        response = await client.get(url)
        response.raise_for_status()
        return response.text


def normalize_domain_url(url: str) -> str:
    parsed = urlparse(url)
    scheme = parsed.scheme or "https"
    netloc = parsed.netloc or parsed.path
    return f"{scheme}://{netloc}"

def lookup_policy_api(domain: str) -> str:
    url = "https://api.search.brave.com/res/v1/web/search"

    querystring = {"q":f"{domain}+privacy+policy"}

    headers = {
        "accept": "application/json",
        "accept-encoding": "gzip",
        "x-subscription-token": S_API_KEY
    }

    response = requests.get(url, headers=headers, params=querystring)

    if response.status_code == 200:
        data = response.json()
        #print(data)
        for result in data.get("web", {}).get("results", []):
            if "privacy" in result.get("url", "").lower():
                #print(result["url"])
                return result["url"]
    else:
        print("Error:", response.status_code, response.text)
    
    return ""
    

async def scrape_for_privacy_policy(base_url: str) -> str:
    try:
        async with httpx.AsyncClient(timeout=10.0) as client:
            response = await client.get(base_url, follow_redirects=True)
            if response.status_code == 200:
                soup = BeautifulSoup(response.text, "html.parser")
                for a_tag in soup.find_all("a", href=True):
                    href = a_tag["href"].lower()
                    if "privacy" in href:
                        policy_url = urljoin(base_url, a_tag["href"])
                        return policy_url
    except Exception:
        pass
    return ""

async def find_privacy_policy_url(domain_url: str) -> str:

    domain_url = normalize_domain_url(domain_url)
    # API 
    parsed = urlparse(domain_url)
    base_domain = parsed.netloc or domain_url
    api_result = lookup_policy_api(base_domain)
    if api_result:
        return api_result

    # URL paths
    parsed = urlparse(domain_url)
    base_domain = parsed.netloc
    base_url = f"{parsed.scheme}://{base_domain}"
    async with httpx.AsyncClient(timeout=5.0, follow_redirects=True) as client:
        for path in COMMON_PRIVACY_PATHS:
            candidate = urljoin(base_url, path)
            try:
                res = await client.get(candidate)
                if res.status_code == 200:
                    return str(res.url)
            except httpx.RequestError:
                continue

    # Scrape
    scraped_url = await scrape_for_privacy_policy(base_url)
    if scraped_url:
        return scraped_url

    return ""

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
    privacy_url = await find_privacy_policy_url(url)
    html = await fetch_html(privacy_url)
    cleaned_text = clean_html(html)
    print(privacy_url)
    if len(cleaned_text.split()) > 8000:
        raise ValueError("Privacy policy is too long to summarize.")

    payload = {
    "contents": [{ "parts": [{ "text": f"You are given a privacy policy text. Analyze it and extract structured information strictly following the JSON schema provided by the API.\n\n**Instructions:**\n- Use only values explicitly mentioned in the policy; if not mentioned, use `null` for strings/arrays and `false` for booleans.\n- Do not add extra fields or text outside the schema.\n- For booleans: return `true` only if the policy explicitly allows or confirms it; otherwise `false`.\n- For arrays: include exact terms from the policy; if none found, return an empty array `[]`.\n- For `summary_text` and `recommendation`, provide concise, plain text summaries (max 2 sentences).\n- Ensure the output is valid JSON and strictly matches the property names and order defined in the schema.\n- Remember this data is consumed by general internet user so answer accordingly.\n\n**Privacy Policy to analyze:**\n\n{cleaned_text}" }] }],
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
                                "can_company_collect_data": { "type": "BOOLEAN" },
                                "is_company_collecting_data": { "type": "BOOLEAN" },
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
    
    print(f"Cleaned text word count: {len(cleaned_text.split())}")
    print(f"Cleaned text preview:\n{cleaned_text}")

    timeout = httpx.Timeout(60.0) #new
    async with httpx.AsyncClient(timeout=timeout) as client:
        response = await client.post(API_URL, headers=headers, json=payload)
        response.raise_for_status()
        try:
            return response.json()["candidates"][0]["content"]["parts"][0]["text"]
        except Exception as e:
            print("Failed to parse Gemini response:", response.json())
            raise e

