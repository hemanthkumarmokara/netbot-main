import sqlite3
import openai
import os
import certifi
import re
import requests
import urllib3
from flask import Flask, request, jsonify, render_template, session, send_file, redirect, url_for, flash
import httpx
from werkzeug.utils import secure_filename
from werkzeug.security import generate_password_hash, check_password_hash


from routing_checker import is_routing_possible
from weekly_updates import answer_weekly_update_question
from logic import parse_text_file, generate_yaml

app = Flask(__name__)
app.secret_key = "your_secret_key_here"  # Required for session storage

# Use latest SSL certificates
os.environ["SSL_CERT_FILE"] = certifi.where()

# Disable SSL verification warnings
urllib3.disable_warnings(urllib3.exceptions.InsecureRequestWarning)

# Define the uploads folder
BASE_DIR = os.path.dirname(os.path.abspath(__file__))
UPLOAD_FOLDER = os.path.join(BASE_DIR, "uploads")
os.makedirs(UPLOAD_FOLDER, exist_ok=True)
app.config['UPLOAD_FOLDER'] = UPLOAD_FOLDER # Store in app config for consistency

# Azure OpenAI API Details
AZURE_OPENAI_API_KEY = "" # Consider using environment variables for keys
AZURE_OPENAI_ENDPOINT = "https://hemanthazureopani.openai.azure.com/"
AZURE_DEPLOYMENT_NAME = "gpt-4"

openai.api_type = "azure"
openai.api_key = AZURE_OPENAI_API_KEY
openai.api_base = AZURE_OPENAI_ENDPOINT
openai.api_version = "2023-12-01-preview"

# Override OpenAI request session to disable SSL verification
# Note: Disabling SSL verification globally is a security risk.
# Prefer configuring httpx.Client(verify=...) where used.
openai.requestssession = requests.Session()
openai.requestssession.verify = False


# --- Database Initialization ---
def init_user_db():
    conn = sqlite3.connect('users.db')
    c = conn.cursor()
    c.execute('''
        CREATE TABLE IF NOT EXISTS users (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            username TEXT NOT NULL UNIQUE,
            password TEXT NOT NULL
        )
    ''')
    conn.commit()
    conn.close()

# --- Authentication Routes ---
@app.route('/', methods=['GET', 'POST'])
def login():
    if 'username' in session: # If already logged in, redirect to netbot
        return redirect(url_for('netbot_home'))
    if request.method == 'POST':
        username = request.form['username']
        password_input = request.form['password']

        conn = sqlite3.connect('users.db')
        c = conn.cursor()
        c.execute("SELECT password FROM users WHERE username = ?", (username,))
        result = c.fetchone()
        conn.close()

        if result and check_password_hash(result[0], password_input):
            session['username'] = username
            return redirect(url_for('netbot_home'))  # Redirect to the main chatbot page
        else:
            flash("Invalid username or password.", "danger")
    return render_template('login.html')

@app.route('/signup', methods=['GET', 'POST'])
def signup():
    if 'username' in session: # If already logged in, redirect to netbot
        return redirect(url_for('netbot_home'))
    if request.method == 'POST':
        username = request.form['username']
        password = request.form['password'] # Get plain password
        
        if not username or not password:
            flash("Username and password are required.", "danger")
            return render_template('signup.html')

        hashed_password = generate_password_hash(password) # Hash the password

        conn = sqlite3.connect('users.db')
        c = conn.cursor()
        try:
            c.execute("INSERT INTO users (username, password) VALUES (?, ?)", (username, hashed_password))
            conn.commit()
            flash("Signup successful. Please log in.", "success")
            return redirect(url_for('login')) # Corrected redirect
        except sqlite3.IntegrityError:
            flash("Username already exists.", "danger")
        finally:
            conn.close()
    return render_template('signup.html')

@app.route('/logout')
def logout():
    session.pop('username', None)
    flash("You have been logged out.", "info")
    return redirect(url_for('login'))

# --- Main Application Routes ---
@app.route('/netbot')
def netbot_home():
    if 'username' not in session:
        return redirect(url_for('login'))
    # This is your main chatbot page
    return render_template('index.html', username=session['username'])

# Removed the conflicting @app.route("/netbot") def home(): route.
# The netbot_home function above now correctly handles /netbot.

# @app.route("/yamlbh", methods=["GET", "POST"])
# def yamlbh_handler(): # Renamed function from 'index' for clarity
#     if request.method == "POST":
#         if "textfile" not in request.files:
#             return "No file part"
        
#         uploaded_file = request.files["textfile"]
#         if uploaded_file.filename == "":
#             return "No selected file"

#         if uploaded_file.filename.endswith(".txt"):
#             filename = secure_filename(uploaded_file.filename)
#             filepath = os.path.join(UPLOAD_FOLDER, filename)
#             uploaded_file.save(filepath)
#             data = parse_text_file(filepath)  # Use the function from logic.py
#             try:
#                 yaml_path = generate_yaml(data)  # Use the function from logic.py
#                 return send_file(yaml_path, as_attachment=True)
#             except Exception as e:
#                 return f"Error generating YAML: {str(e)}"
#         else:
#             return "Please upload a valid .txt file."
#     return render_template("index.html")

# --- API Routes / Backend Logic ---

def extract_ips(text):
    ip_pattern = r"\b(?:\d{1,3}\.){3}\d{1,3}\b"
    return re.findall(ip_pattern, text)

@app.route("/chat", methods=["POST"])
def chat():
    if 'username' not in session: # API endpoints should also be protected
         return jsonify({"error": "Unauthorized"}), 401

    # File upload part for YAML generation (if submitted to /chat instead of /yamlbh)
    # Consider if this functionality should be exclusively in /yamlbh
    if "textfile" in request.files:
        uploaded_file = request.files["textfile"]
        if uploaded_file and uploaded_file.filename != "" and uploaded_file.filename.endswith(".txt"):
            try:
                filename = secure_filename(uploaded_file.filename)
                filepath = os.path.join(app.config['UPLOAD_FOLDER'], filename)
                uploaded_file.save(filepath)
                
                data = parse_text_file(filepath)
                yaml_path = generate_yaml(data) # Pass UPLOAD_FOLDER
                
                # Optional: clean up uploaded .txt file
                # if os.path.exists(filepath): os.remove(filepath)
                
                return send_file(yaml_path, as_attachment=True)
            except Exception as e:
                # print(f"Error processing file for YAML: {e}") # Log error
                return jsonify({"error": f"Error processing file for YAML: {str(e)}"}), 500
        else:
            return jsonify({"error": "Invalid or no .txt file provided for YAML generation."}), 400
    
    # Process as a regular chat message
    user_input = request.form.get("message")
    if not user_input:
        return jsonify({"error": "Message cannot be empty if no file is sent"}), 400

    # Weekly update query
    if "update" in user_input.lower() and \
       ("week" in user_input.lower() or \
        re.search(r"(march|april|may|june|july|august|september|october|november|december)", user_input.lower(), re.IGNORECASE)): # Added re.IGNORECASE
        
        gpt_response_text = get_weekly_update_from_gpt(user_input)
        if gpt_response_text and "Error:" not in gpt_response_text : # Basic check for error from GPT func
            # Try to parse department and week, then call answer_weekly_update_question
            match = re.search(r"Update for (.*?) during (.*?):(.*)", gpt_response_text, re.IGNORECASE) # Check for optional content
            if match:
                department = match.group(1).strip()
                week = match.group(2).strip()
                # Call your function that queries the actual data
                update_content = answer_weekly_update_question(department, week)
                if "No update found" in update_content or "Error" in update_content : # Check specific response
                     return jsonify({"response": f"I looked for an update for {department} for {week}. {update_content}"})
                return jsonify({"response": f"Update for {department} during {week}: {update_content}"})
            else:
                # If GPT itself provides the full answer and we don't need to call answer_weekly_update_question
                if "Update for" in gpt_response_text and ":" in gpt_response_text:
                     return jsonify({"response": gpt_response_text})
                return jsonify({"response": "Sorry, I couldn't extract the department and week properly for the update from the information I got."})
        else:
            return jsonify({"response": gpt_response_text or "Sorry, I had trouble fetching that update."})

    # IP address extraction and routing check
    extracted_ips = extract_ips(user_input)
    stored_ip = session.get("stored_ip", None)
    source_ip, destination_ip = "N/A", "N/A"

    if len(extracted_ips) == 2:
        source_ip, destination_ip = extracted_ips
        session.pop("stored_ip", None)
    elif len(extracted_ips) == 1:
        if stored_ip:
            source_ip, destination_ip = stored_ip, extracted_ips[0]
            session.pop("stored_ip", None)
        else:
            session["stored_ip"] = extracted_ips[0]
            # OpenAI will be prompted to ask for the second IP.
    
    # OpenAI call for general chat
    chat_prompt = [
        {
            "role": "system",
            "content": (
                "You are NetBot, a GWAN assistant that helps users check network routing and diagnose connectivity issues.\n\n"
                "Your tasks:\n"
                "- Guide users in finding routing paths.\n"
                "- Request missing IP addresses when needed. If one IP is given, ask for the second one or what to do with the single IP.\n"
                "- Provide answers based on networking best practices.\n\n"
                "**Examples:**\n"
                "- User: 'Is 12.3.46.4 reachable?'\n"
                "  - NetBot: 'You provided only one IP: 12.3.46.4. Please enter the source IP or destination IP to check reachability, or clarify what you'd like to do with this IP.'\n"
                "- User: 'Check route between 10.1.1.1 and 10.2.2.2'\n"
                "  - NetBot: 'Okay, I will check the routing between 10.1.1.1 and 10.2.2.2.' (Then backend provides routing_result)\n"
                "- User: '32.2.34.2'\n"
                "  - NetBot: 'You provided only one IP: 32.2.34.2. To check routing, I need a source and destination IP. What would you like to do with this IP?'\n"
            )
        },
        {"role": "user", "content": user_input}
    ]
    try:
        # It's better to disable SSL verification per client instance
        with httpx.Client(verify=False) as http_client:
            client = openai.AzureOpenAI(
                api_key=AZURE_OPENAI_API_KEY, api_version=openai.api_version,
                azure_endpoint=AZURE_OPENAI_ENDPOINT, http_client=http_client
            )
            response = client.chat.completions.create(
                model=AZURE_DEPLOYMENT_NAME, messages=chat_prompt, temperature=0.7
            )
        bot_reply = response.choices[0].message.content

        routing_info = ""
        if source_ip != "N/A" and destination_ip != "N/A":
            routing_result = is_routing_possible(source_ip, destination_ip) # Ensure this function exists
            routing_info = f"\n\n➡️ Routing Check Result for {source_ip} to {destination_ip}: {routing_result}"
        
        final_reply = bot_reply + routing_info
            
        return jsonify({
            "response": final_reply,
            "source_ip": source_ip,
            "destination_ip": destination_ip 
        })
    except Exception as e:
        # print(f"OpenAI API Error: {e}") # Log error
        return jsonify({"error": f"Error communicating with AI model: {str(e)}"}), 500


def get_weekly_update_from_gpt(question):
    # This function now primarily serves to structure the prompt for GPT
    # to understand it's a weekly update question. The actual data fetching
    # should be done by `answer_weekly_update_question`.
    chat_prompt = [
        {
            "role": "system",
            "content": (
                "You are an assistant that helps parse requests for weekly updates. "
                "The user will ask about an update for a department for a specific week. "
                "Your role is to confirm understanding and structure the request, "
                "but DO NOT try to invent or provide the update yourself. "
                "Just acknowledge and rephrase the request in the format: "
                "'Update for [department] during [week]: [Placeholder for actual update data]'. "
                "If you cannot identify the department or week, say so."
                "\nExamples of user questions:\n"
                "- 'What is the update on AUD for the week Mar 31 - Apr 4, 2025?' -> 'Update for AUD during Mar 31 - Apr 4, 2025: [Placeholder for actual update data]'\n"
                "- 'Give me the update of GWAN for March 31 - April 4, 2025.' -> 'Update for GWAN during March 31 - April 4, 2025: [Placeholder for actual update data]'\n"
            )
        },
        {"role": "user", "content": question}
    ]
    try:
        with httpx.Client(verify=False) as http_client: # Disable SSL verification for this client
            client = openai.AzureOpenAI(
                api_key=AZURE_OPENAI_API_KEY,
                api_version=openai.api_version,
                azure_endpoint=AZURE_OPENAI_ENDPOINT,
                http_client=http_client
            )
            response = client.chat.completions.create(
                model=AZURE_DEPLOYMENT_NAME,
                messages=chat_prompt,
                temperature=0.2 # Lower temperature for more deterministic parsing
            )
        return response.choices[0].message.content
    except Exception as e:
        # print(f"Error in get_weekly_update_from_gpt: {e}") # Log error
        return f"Error: Could not process the update request with GPT ({str(e)})"


# @app.route("/ask", methods=["POST"]) # This route seems specific and might be redundant with /chat's weekly update logic
# def ask():
#     if 'username' not in session: # API endpoints should also be protected
#          return jsonify({"error": "Unauthorized"}), 401

#     data = request.get_json() # Expect JSON input
#     if not data or "message" not in data:
#         return jsonify({"error": "Message cannot be empty and must be in JSON format"}), 400
    
#     question = data["message"]

#     # This regex is very specific. Consider if get_weekly_update_from_gpt + answer_weekly_update_question in /chat is preferred.
#     match = re.search(r"update on ([\w\s]+) for the week ([\w\s\d,-]+)", question, re.IGNORECASE)
#     if match:
#         department = match.group(1).strip()
#         date_range = match.group(2).strip()
#         try:
#             update = answer_weekly_update_question(department, date_range) # Ensure this function exists
#             if "No update found" in update or "Error" in update:
#                  return jsonify({"response": update})
#             return jsonify({"response": f"The update for {department} from {date_range} is: {update}"})
#         except Exception as e:
#             # print(f"Error fetching update in /ask: {e}") # Log error
#             return jsonify({"error": f"Error fetching update: {str(e)}"}), 500
#     else:
#         # Fallback to GPT if direct parsing fails or use a more generic response.
#         gpt_response = get_weekly_update_from_gpt(question)
#         if "Error:" not in gpt_response:
#              # Attempt to extract and use answer_weekly_update_question as in /chat
#             gpt_match = re.search(r"Update for (.*?) during (.*?):", gpt_response, re.IGNORECASE)
#             if gpt_match:
#                 department = gpt_match.group(1).strip()
#                 week = gpt_match.group(2).strip()
#                 update_content = answer_weekly_update_question(department, week)
#                 if "No update found" in update_content or "Error" in update_content:
#                     return jsonify({"response": f"I looked for an update for {department} for {week}. {update_content}"})
#                 return jsonify({"response": f"Update for {department} during {week}: {update_content}"})
#             return jsonify({"response": "I could parse your request with Netbot but couldn't confirm the department/week for a direct lookup. The AI said: " + gpt_response})
#         return jsonify({"response": "I couldn't understand the question format. Please ask like: 'What is the update for [Department] for the week [Date range]?' or use the main chat."})


if __name__ == '__main__':
    init_user_db()
    app.run(debug=True, host='0.0.0.0', port=5000) # Example: run on all interfaces, port 5000