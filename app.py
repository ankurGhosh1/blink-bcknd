# from flask import Flask, request, jsonify
# from flask_cors import CORS
# import requests
# from bs4 import BeautifulSoup
# import csv
# from io import StringIO
# from groq import Groq
# import os
# from dotenv import load_dotenv

# # Load environment variables
# load_dotenv()

# app = Flask(__name__)
# CORS(app)

# # API keys from environment variables
# app.config['GROQ_API_KEY'] = os.getenv("GROQ_API_KEY")
# app.config['RAPID_API_KEY'] = os.getenv("RAPID_API_KEY")
# app.config['HUNTER_API_KEY'] = os.getenv("HUNTER_API_KEY")
# app.config['SNOV_API_KEY'] = os.getenv("SNOV_API_KEY")

# # API endpoint details
# RAPIDAPI_KEY = app.config['RAPID_API_KEY']
# RAPIDAPI_HOST = "ahrefs2.p.rapidapi.com"
# AUTHORITY_URL = "https://ahrefs2.p.rapidapi.com/authority"
# TRAFFIC_URL = "https://ahrefs2.p.rapidapi.com/website-traffic"
# HUNTER_URL = "https://api.hunter.io/v2/domain-search"
# SNOV_START_URL = "https://api.snov.io/v2/domain-search/prospects/start"
# SNOV_RESULT_URL = "https://api.snov.io/v2/domain-search/result/"

# # Groq API setup
# groq_client = Groq(api_key=app.config['GROQ_API_KEY'])

# # Predefined industries
# INDUSTRIES = [
#     "Technology", "Marketing", "Health", "Finance",
#     "E-commerce", "Education", "Entertainment", "Other"
# ]

# def fetch_ahrefs_data(domain):
#     """Fetch DR from Ahrefs endpoint, traffic commented out."""
#     headers = {
#         "X-RapidAPI-Key": RAPIDAPI_KEY,
#         "X-RapidAPI-Host": RAPIDAPI_HOST
#     }
#     params = {"url": domain, "mode": "subdomains"}
    
#     # Fetch DR
#     dr = 0
#     try:
#         print(f"Fetching DR for {domain} from {AUTHORITY_URL} with params: {params}")
#         response = requests.get(AUTHORITY_URL, headers=headers, params=params, timeout=10)
#         response.raise_for_status()
#         data = response.json()
#         print(f"Authority response for {domain}: {data}")
#         dr = data.get("domainRating", 0)
#     except Exception as e:
#         print(f"Error fetching DR for {domain}: {e}")
    
#     # Traffic commented out as requested
#     # traffic = 0
#     # try:
#     #     print(f"Fetching traffic for {domain} from {TRAFFIC_URL} with params: {params}")
#     #     traffic_response = requests.get(TRAFFIC_URL, headers=headers, params=params, timeout=10)
#     #     traffic_response.raise_for_status()
#     #     traffic_data = traffic_response.json()
#     #     print(f"Traffic response for {domain}: {traffic_data}")
#     #     traffic = traffic_data.get("traffic", 0)
#     # except Exception as e:
#     #     print(f"Error fetching traffic for {domain}: {e}")
    
#     return {"dr": dr, "traffic": 0}

# def scrape_content(domain):
#     """Scrape basic content from a domain’s homepage."""
#     try:
#         response = requests.get(f"https://{domain}", timeout=5)
#         response.raise_for_status()
#         soup = BeautifulSoup(response.text, "html.parser")
#         title = soup.title.string if soup.title else ""
#         meta_desc = soup.find("meta", {"name": "description"})["content"] if soup.find("meta", {"name": "description"}) else ""
#         first_p = soup.find("p").text if soup.find("p") else ""
#         return f"{title} {meta_desc} {first_p}".strip()
#     except Exception as e:
#         print(f"Error scraping {domain}: {e}")
#         return "Unable to scrape"

# def classify_industry(content):
#     """Classify industry using Groq, expecting only the category name."""
#     if not content or "unable to scrape" in content:
#         return "Other"
    
#     prompt = (
#         f"Classify the industry of this website based on the following content into one of these categories: "
#         f"{', '.join(INDUSTRIES)}. Respond with only the category name, nothing else. Content: {content}"
#     )
#     try:
#         print(f"Classifying industry for content: {content[:50]}...")
#         response = groq_client.chat.completions.create(
#             model="mixtral-8x7b-32768",
#             messages=[{"role": "user", "content": prompt}],
#             max_tokens=10,
#             temperature=0.5
#         )
#         industry = response.choices[0].message.content.strip()
#         print(f"Groq classified industry as: {industry}")
#         return industry if industry in INDUSTRIES else "Other"
#     except Exception as e:
#         print(f"Error classifying industry: {e}")
#         return "Other"

# def calculate_relevancy(target_content, domain_content, target_industry, domain_industry):
#     """Determine relevancy based on content overlap and industry match."""
#     if not target_content or not domain_content or "unable to scrape" in domain_content:
#         return "Low", 30
    
#     target_words = set(target_content.lower().split())
#     domain_words = set(domain_content.lower().split())
#     overlap = len(target_words & domain_words) / max(len(target_words), 1) * 100
    
#     industry_match = target_industry == domain_industry
    
#     if industry_match and overlap > 20:
#         return "High", 80
#     elif industry_match or overlap > 10:
#         return "Medium", 60
#     return "Low", 30

# def process_domains(target_domain, target_industry, csv_file):
#     """Process domains and calculate combined score."""
#     results = []
#     target_content = scrape_content(target_domain)
    
#     csv_text = csv_file.read().decode("utf-8")
#     csv_reader = csv.reader(StringIO(csv_text))
#     domains = [row[0] for row in csv_reader if row]
    
#     for domain in domains:
#         ahrefs_data = fetch_ahrefs_data(domain)
#         dr = ahrefs_data["dr"]
#         traffic = ahrefs_data["traffic"]
        
#         domain_content = scrape_content(domain)
#         industry = classify_industry(domain_content)
        
#         relevancy, relevancy_score = calculate_relevancy(target_content, domain_content, target_industry, industry)
        
#         combined_score = (dr / 100 * 50) + (relevancy_score / 100 * 50)
        
#         results.append({
#             "domain": domain,
#             "traffic": traffic,
#             "dr": dr,
#             "industry": industry,
#             "relevancy": relevancy,
#             "score": round(combined_score, 1)
#         })
    
#     return results

# @app.route("/analyze", methods=["POST"])
# def analyze_domains():
#     """API endpoint to handle domain analysis."""
#     if "csv_file" not in request.files or "target_domain" not in request.form or "target_industry" not in request.form:
#         return jsonify({"error": "Missing target domain, industry, or CSV file"}), 400
    
#     target_domain = request.form["target_domain"]
#     target_industry = request.form["target_industry"]
#     csv_file = request.files["csv_file"]
    
#     if target_industry not in INDUSTRIES:
#         return jsonify({"error": "Invalid industry"}), 400
    
#     try:
#         results = process_domains(target_domain, target_industry, csv_file)
#         return jsonify({"results": results})
#     except Exception as e:
#         return jsonify({"error": f"Processing failed: {str(e)}"}), 500

# @app.route("/find-contacts", methods=["POST"])
# def find_contacts():
#     """Fetch one email using Hunter.io and Snov.io, no department/position filters."""
#     domains = request.json.get("domains", [])
#     hunter_api_key = app.config['HUNTER_API_KEY']
#     snov_api_key = app.config['SNOV_API_KEY']
#     contacts = []
    
#     for domain in domains:
#         contact_data = {
#             "domain": domain,
#             "contact_email": "Not found",
#             "first_name": "",
#             "last_name": "",
#             "job_title": "",
#             "linkedin_url": ""
#         }
        
#         # Hunter.io: Fetch one email (1 credit), no department filter
#         try:
#             params = {
#                 "domain": domain,
#                 "api_key": hunter_api_key,
#                 "limit": 1  # One email only
#             }
#             print(f"Fetching Hunter.io email for {domain}")
#             response = requests.get(HUNTER_URL, params=params, timeout=10)
#             response.raise_for_status()
#             data = response.json()
#             print(f"Hunter.io response for {domain}: {data}")
#             emails = data.get("data", {}).get("emails", [])
#             if emails:
#                 contact_data["contact_email"] = emails[0].get("value", "Not found")
#                 contact_data["first_name"] = emails[0].get("first_name", "")
#                 contact_data["last_name"] = emails[0].get("last_name", "")
#         except Exception as e:
#             print(f"Error fetching Hunter.io email for {domain}: {e}")
        
#         # Snov.io: Fetch one prospect email (1 credit), no position filter
#         # try:
#         #     payload = {
#         #         "domain": domain,
#         #         "limit": 1,  # One prospect only
#         #         "access_token": snov_api_key
#         #     }
#         #     print(f"Starting Snov.io prospect search for {domain}")
#         #     start_response = requests.post(SNOV_START_URL, json=payload, timeout=10)
#         #     start_response.raise_for_status()
#         #     start_data = start_response.json()
#         #     print(f"Snov.io start response for {domain}: {start_data}")
#         #     task_hash = start_data.get("task_hash")
            
#         #     if task_hash:
#         #         result_url = f"{SNOV_RESULT_URL}{task_hash}"
#         #         print(f"Fetching Snov.io result for {domain} from {result_url}")
#         #         result_response = requests.get(result_url, params={"access_token": snov_api_key}, timeout=10)
#         #         result_response.raise_for_status()
#         #         result_data = result_response.json()
#         #         print(f"Snov.io result response for {domain}: {result_data}")
                
#         #         prospects = result_data.get("prospects", [])
#         #         if prospects:
#         #             prospect = prospects[0]
#         #             emails = prospect.get("emails", [])
#         #             if emails and emails[0].get("status") == "verified":
#         #                 contact_data["contact_email"] = emails[0].get("email", contact_data["contact_email"])
#         #             contact_data["first_name"] = prospect.get("first_name", contact_data["first_name"])
#         #             contact_data["last_name"] = prospect.get("last_name", contact_data["last_name"])
#         #             contact_data["job_title"] = prospect.get("position", "")
#         #             social_links = prospect.get("social_links", [])
#         #             for link in social_links:
#         #                 if "linkedin.com" in link:
#         #                     contact_data["linkedin_url"] = link
#         #                     break
#         # except Exception as e:
#         #     print(f"Error fetching Snov.io data for {domain}: {e}")
        
#         contacts.append(contact_data)
    
#     return jsonify({"contacts": contacts})

# if __name__ == "__main__":
#     app.run(debug=True, host="0.0.0.0", port=5000)

#######
# V2  #
#######

from flask import Flask, request, jsonify
from flask_cors import CORS
import requests
from bs4 import BeautifulSoup
import csv
from io import StringIO
from groq import Groq
import os
from dotenv import load_dotenv
import json

# Load environment variables
load_dotenv()

app = Flask(__name__)
CORS(app)

# API keys from environment variables
app.config['GROQ_API_KEY'] = os.getenv("GROQ_API_KEY")
app.config['RAPID_API_KEY'] = os.getenv("RAPID_API_KEY")

# API endpoint details
RAPIDAPI_KEY = app.config['RAPID_API_KEY']
RAPIDAPI_HOST = "ahrefs1.p.rapidapi.com"
DR_URL = "/v1/website-authority-checker"
TRAFFIC_URL = "/v1/website-traffic-checker"

# Groq API setup
groq_client = Groq(api_key=app.config['GROQ_API_KEY'])

# Predefined industries
INDUSTRIES = [
    "Technology", "Marketing", "Health", "Finance",
    "E-commerce", "Education", "Entertainment", "Other"
]

def fetch_ahrefs_data(domain):
    """Fetch DR and traffic data from Ahrefs APIs."""
    headers = {
        "X-RapidAPI-Key": RAPIDAPI_KEY,
        "X-RapidAPI-Host": RAPIDAPI_HOST
    }
    
    # Fetch Domain Rating (DR)
    dr_data = {"status": "error", "error": "Failed to fetch DR"}
    try:
        dr_params = {"url": domain, "mode": "subdomains"}
        response = requests.get(f"https://{RAPIDAPI_HOST}{DR_URL}", headers=headers, params=dr_params, timeout=10)
        response.raise_for_status()
        dr_data = response.json()
        if dr_data.get("status") != "success":
            dr_data = {"status": "error", "error": "Invalid DR response"}
    except requests.exceptions.RequestException as e:
        print(f"Error fetching DR for {domain}: {str(e)}")
    
    # Fetch Traffic Data
    traffic_data = {"status": "error", "error": "Failed to fetch traffic"}
    try:
        traffic_params = {"url": domain, "mode": "subdomains"}
        response = requests.get(f"https://{RAPIDAPI_HOST}{TRAFFIC_URL}", headers=headers, params=traffic_params, timeout=10)
        response.raise_for_status()
        traffic_data = response.json()
        if traffic_data.get("status") != "success":
            traffic_data = {"status": "error", "error": "Invalid traffic response"}
    except requests.exceptions.RequestException as e:
        print(f"Error fetching traffic data for {domain}: {str(e)}")
    
    # Construct response based on dummy structure
    result = {
        "dr": dr_data.get("overview", {}).get("domainRating", 0) if dr_data.get("status") == "success" else 0,
        "url_rating": dr_data.get("overview", {}).get("urlRating", 0) if dr_data.get("status") == "success" else 0,
        "backlinks": dr_data.get("overview", {}).get("backlinks", 0) if dr_data.get("status") == "success" else 0,
        "refdomains": dr_data.get("overview", {}).get("refdomains", 0) if dr_data.get("status") == "success" else 0,
        "dofollow_backlinks": dr_data.get("overview", {}).get("dofollowBacklinks", 0) if dr_data.get("status") == "success" else 0,
        "dofollow_refdomains": dr_data.get("overview", {}).get("dofollowRefdomains", 0) if dr_data.get("status") == "success" else 0,
        "traffic_history": traffic_data.get("traffic_history", []),
        "traffic_monthly_avg": traffic_data.get("traffic", {}).get("trafficMonthlyAvg", 0),
        "traffic_cost_monthly_avg": traffic_data.get("traffic", {}).get("costMontlyAvg", 0),
        "top_pages": traffic_data.get("top_pages", []),
        "top_countries": traffic_data.get("top_countries", []),
        "top_keywords": traffic_data.get("top_keywords", [])
    }
    
    return result

def scrape_content(domain):
    """Scrape basic content from a domain’s homepage."""
    try:
        response = requests.get(f"https://{domain}", timeout=5)
        response.raise_for_status()
        soup = BeautifulSoup(response.text, "html.parser")
        title = soup.title.string if soup.title else ""
        meta_desc = soup.find("meta", {"name": "description"})["content"] if soup.find("meta", {"name": "description"}) else ""
        first_p = soup.find("p").text if soup.find("p") else ""
        return f"{title} {meta_desc} {first_p}".strip()
    except Exception as e:
        print(f"Error scraping {domain}: {str(e)}")
        return "Unable to scrape"

def classify_industry(content):
    """Classify industry using Groq, returning only the category name."""
    if not content or "unable to scrape" in content:
        return "Other"
    
    prompt = (
        f"Classify the industry of this website based on the following content into one of these categories: "
        f"{', '.join(INDUSTRIES)}. Respond with only the category name, nothing else. Content: {content}"
    )
    try:
        response = groq_client.chat.completions.create(
            model="mixtral-8x7b-32768",
            messages=[{"role": "user", "content": prompt}],
            max_tokens=10,
            temperature=0.5
        )
        industry = response.choices[0].message.content.strip()
        return industry if industry in INDUSTRIES else "Other"
    except Exception as e:
        print(f"Error classifying industry: {e}")
        return "Other"

def calculate_relevancy(target_content, domain_content, target_industry, domain_industry):
    """Determine relevancy based on content overlap and industry match."""
    if not target_content or not domain_content or "unable to scrape" in domain_content:
        return "Low", 30
    
    target_words = set(target_content.lower().split())
    domain_words = set(domain_content.lower().split())
    overlap = len(target_words & domain_words) / max(len(target_words), 1) * 100
    
    industry_match = target_industry == domain_industry
    
    if industry_match and overlap > 20:
        return "High", 80
    elif industry_match or overlap > 10:
        return "Medium", 60
    return "Low", 30

def process_domains(target_domain, target_industry, csv_file):
    """Process domains and calculate combined score."""
    results = []
    target_content = scrape_content(target_domain)
    
    csv_text = csv_file.read().decode("utf-8")
    csv_reader = csv.reader(StringIO(csv_text))
    domains = [row[0] for row in csv_reader if row]
    
    for domain in domains:
        ahrefs_data = fetch_ahrefs_data(domain)
        dr = ahrefs_data["dr"]
        url_rating = ahrefs_data["url_rating"]
        backlinks = ahrefs_data["backlinks"]
        refdomains = ahrefs_data["refdomains"]
        dofollow_backlinks = ahrefs_data["dofollow_backlinks"]
        dofollow_refdomains = ahrefs_data["dofollow_refdomains"]
        traffic_history = ahrefs_data["traffic_history"]
        traffic_monthly_avg = ahrefs_data["traffic_monthly_avg"]
        traffic_cost_monthly_avg = ahrefs_data["traffic_cost_monthly_avg"]
        top_pages = ahrefs_data["top_pages"]
        top_countries = ahrefs_data["top_countries"]
        top_keywords = ahrefs_data["top_keywords"]
        
        domain_content = scrape_content(domain)
        industry = classify_industry(domain_content)
        
        relevancy, relevancy_score = calculate_relevancy(target_content, domain_content, target_industry, industry)
        
        combined_score = (dr / 100 * 50) + (relevancy_score / 100 * 50)
        
        results.append({
            "domain": domain,
            "dr": dr,
            "url_rating": url_rating,
            "backlinks": backlinks,
            "refdomains": refdomains,
            "dofollow_backlinks": dofollow_backlinks,
            "dofollow_refdomains": dofollow_refdomains,
            "traffic_history": traffic_history,
            "traffic_monthly_avg": traffic_monthly_avg,
            "traffic_cost_monthly_avg": traffic_cost_monthly_avg,
            "top_pages": top_pages,
            "top_countries": top_countries,
            "top_keywords": top_keywords,
            "industry": industry,
            "relevancy": relevancy,
            "score": round(combined_score, 1)
        })
    
    return results

@app.route("/analyze", methods=["POST"])
def analyze_domains():
    """API endpoint to handle domain analysis."""
    if "csv_file" not in request.files or "target_domain" not in request.form or "target_industry" not in request.form:
        return jsonify({"error": "Missing target domain, industry, or CSV file"}), 400
    
    target_domain = request.form["target_domain"]
    target_industry = request.form["target_industry"]
    csv_file = request.files["csv_file"]
    
    if target_industry not in INDUSTRIES:
        return jsonify({"error": "Invalid industry"}), 400
    
    try:
        results = process_domains(target_domain, target_industry, csv_file)
        return jsonify({"results": results})
    except Exception as e:
        return jsonify({"error": f"Processing failed: {str(e)}"}), 500

if __name__ == "__main__":
    app.run(debug=True, host="0.0.0.0", port=5000)