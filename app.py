from flask import Flask, request, jsonify, g
from flask_cors import CORS
import requests
from bs4 import BeautifulSoup
import csv
from io import StringIO
from groq import Groq
import os
from dotenv import load_dotenv
import psycopg2
from sendgrid import SendGridAPIClient
from sendgrid.helpers.mail import Mail, To

# Load environment variables
load_dotenv()

app = Flask(__name__)
# Allow multiple origins: localhost for development, and the deployed frontend URL
allowed_origins = [
    "http://localhost:3000",  # Development
    "https://blink-fntd.vercel.app",  # Vercel deployment (replace with your frontend URL)
    # Add your custom domain in production, e.g., "https://frontend.yourdomain.com"
]
CORS(app, resources={r"/*": {"origins": allowed_origins}})

# API keys from environment variables
app.config['GROQ_API_KEY'] = os.getenv("GROQ_API_KEY")
app.config['RAPID_API_KEY'] = os.getenv("RAPID_API_KEY")
app.config['HUNTER_API_KEY'] = os.getenv("HUNTER_API_KEY")
app.config['SENDGRID_API_KEY'] = os.getenv("SENDGRID_API_KEY")

# API endpoint details
RAPIDAPI_KEY = app.config['RAPID_API_KEY']
RAPIDAPI_HOST = "ahrefs1.p.rapidapi.com"
DR_URL = "/v1/website-authority-checker"
TRAFFIC_URL = "/v1/website-traffic-checker"
HUNTER_API_URL = "https://api.hunter.io/v2/domain-search"

# Groq API setup
groq_client = Groq(api_key=app.config['GROQ_API_KEY'])

# Predefined industries
INDUSTRIES = [
    "Technology", "Marketing", "Health", "Finance",
    "E-commerce", "Education", "Entertainment", "Other"
]

# Database connection management
def get_db():
    if 'db' not in g:
        g.db = psycopg2.connect(os.getenv("NEON_DB_CONNECTION_STRING"))
    return g.db

@app.teardown_appcontext
def close_db(e=None):
    db = g.pop('db', None)
    if db is not None:
        db.close()

# Initialize database schema
def init_db():
    db = get_db()
    cursor = db.cursor()
    cursor.execute("""
        CREATE TABLE IF NOT EXISTS contacts (
            id SERIAL PRIMARY KEY,
            website VARCHAR(255),
            first_name VARCHAR(255),
            last_name VARCHAR(255),
            email VARCHAR(255),
            linkedin VARCHAR(255),
            role VARCHAR(255)
        )
    """)
    db.commit()
    cursor.close()

# Call init_db when the app starts
with app.app_context():
    init_db()

def fetch_ahrefs_data(domain):
    """Fetch DR and traffic data from Ahrefs APIs."""
    headers = {
        "X-RapidAPI-Key": RAPIDAPI_KEY,
        "X-RapidAPI-Host": RAPIDAPI_HOST
    }
    
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

def fetch_emails(domain):
    """Fetch email contacts from database or Hunter API."""
    db = get_db()
    cursor = db.cursor()
    cursor.execute(
        "SELECT DISTINCT first_name, last_name, email, linkedin, role FROM contacts WHERE website = %s",
        (domain,)
    )
    rows = cursor.fetchall()
    if rows:
        # Return list of contacts from database
        result = [{"first_name": row[0], "last_name": row[1], "email": row[2], "linkedin": row[3], "role": row[4], "website": domain} for row in rows]
        cursor.close()
        return result
    else:
        # Call Hunter API if no data in database
        headers = {"Authorization": f"Bearer {app.config['HUNTER_API_KEY']}"}
        params = {"domain": domain, "limit": 10}
        try:
            response = requests.get(HUNTER_API_URL, headers=headers, params=params, timeout=10)
            response.raise_for_status()
            data = response.json()
            emails = data.get("data", {}).get("emails", [])
            if emails:
                # Store each email in the database
                for email_data in emails:
                    cursor.execute("""
                        INSERT INTO contacts (website, first_name, last_name, email, linkedin, role)
                        VALUES (%s, %s, %s, %s, %s, %s)
                        ON CONFLICT (email) DO NOTHING
                    """, (
                        domain,
                        email_data.get("first_name", ""),
                        email_data.get("last_name", ""),
                        email_data.get("value", ""),
                        email_data.get("sources", [{}])[0].get("uri", ""),
                        email_data.get("position", "")
                    ))
                db.commit()
                # Return the fetched emails
                result = [
                    {
                        "first_name": e.get("first_name", ""),
                        "last_name": e.get("last_name", ""),
                        "email": e.get("value", ""),
                        "linkedin": e.get("sources", [{}])[0].get("uri", ""),
                        "role": e.get("position", ""),
                        "website": domain
                    } for e in emails
                ]
                cursor.close()
                return result
            cursor.close()
            return []
        except requests.exceptions.RequestException as e:
            print(f"Error fetching emails for {domain}: {str(e)}")
            cursor.close()
            return []

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
            model="gemma2-9b-it",
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
        emails = fetch_emails(domain)
        
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
            "emails": emails,
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

@app.route("/fetch-emails/<domain>", methods=["GET"])
def fetch_domain_emails(domain):
    """API endpoint to fetch emails for a specific domain."""
    emails = fetch_emails(domain)
    return jsonify({"domain": domain, "emails": emails})

@app.route("/send-email", methods=["POST"])
def send_email():
    """API endpoint to send bulk emails using SendGrid."""
    data = request.get_json()
    to_emails = data.get("to")  # List of recipient emails
    from_email = data.get("from")
    subject = data.get("subject")
    body = data.get("body")

    if not all([to_emails, from_email, subject, body]):
        return jsonify({"error": "Missing required fields"}), 400

    if not isinstance(to_emails, list):
        return jsonify({"error": "Recipient emails must be a list"}), 400

    try:
        # Initialize SendGrid client
        sg = SendGridAPIClient(app.config['SENDGRID_API_KEY'])

        # Create the email message
        message = Mail(
            from_email=from_email,
            subject=subject,
            plain_text_content=body
        )

        # Add multiple recipients
        message.to = [To(email) for email in to_emails]

        # Send the email
        response = sg.send(message)
        return jsonify({"message": "Email sent successfully", "status_code": response.status_code})
    except Exception as e:
        return jsonify({"error": f"Failed to send email: {str(e)}"}), 500

# New route to upload CSV and push to Neon database

@app.route("/upload-contacts", methods=["POST"])
def upload_contacts():
    """API endpoint to upload a CSV file and insert contacts into the Neon database."""
    if "csv_file" not in request.files:
        return jsonify({"error": "No CSV file provided"}), 400

    csv_file = request.files["csv_file"]
    if not csv_file.filename.endswith('.csv'):
        return jsonify({"error": "File must be a CSV"}), 400

    try:
        # Read the CSV file
        csv_text = csv_file.read().decode("utf-8")
        csv_reader = csv.DictReader(StringIO(csv_text))

        # Normalize headers to lowercase for case-insensitive comparison
        if csv_reader.fieldnames is None:
            return jsonify({"error": "CSV file is empty or invalid"}), 400
        normalized_fieldnames = [field.lower() for field in csv_reader.fieldnames]

        # Validate required headers (case-insensitive)
        required_headers = {"website", "first_name", "last_name", "email", "linkedin", "role"}
        if not required_headers.issubset(normalized_fieldnames):
            return jsonify({"error": f"CSV must contain headers: {', '.join(required_headers)}"}), 400

        db = get_db()
        cursor = db.cursor()
        inserted_rows = 0

        # Insert each row into the contacts table
        for row in csv_reader:
            # Map the row keys to lowercase to match the database fields
            normalized_row = {k.lower(): v for k, v in row.items()}
            cursor.execute("""
                INSERT INTO contacts (website, first_name, last_name, email, linkedin, role)
                VALUES (%s, %s, %s, %s, %s, %s)
            """, (
                normalized_row["website"],
                normalized_row["first_name"],
                normalized_row["last_name"],
                normalized_row["email"],
                normalized_row["linkedin"],
                normalized_row["role"]
            ))
            inserted_rows += 1

        db.commit()
        cursor.close()
        return jsonify({"status": "success", "message": f"Inserted {inserted_rows} contacts into the database"})
    except Exception as e:
        return jsonify({"error": f"Failed to process CSV: {str(e)}"}), 500
    
@app.route("/get-contacts", methods=["GET"])
def get_contacts():
    """API endpoint to fetch all contacts from the database."""
    try:
        db = get_db()
        cursor = db.cursor()
        cursor.execute("SELECT website, first_name, last_name, email, linkedin, role FROM contacts")
        rows = cursor.fetchall()
        contacts = [
            {
                "website": row[0],
                "first_name": row[1],
                "last_name": row[2],
                "email": row[3],
                "linkedin": row[4],
                "role": row[5]
            }
            for row in rows
        ]
        cursor.close()
        return jsonify({"contacts": contacts})
    except Exception as e:
        return jsonify({"error": f"Failed to fetch contacts: {str(e)}"}), 500

if __name__ == "__main__":
    app.run(debug=True, host="0.0.0.0", port=5000)