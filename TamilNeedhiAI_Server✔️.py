import os
import requests
from flask import Flask, request, jsonify
from flask_cors import CORS
from groq import Groq

app = Flask(__name__)
CORS(app)

# --- CONFIGURATION ---
SEARCH_ENGINE_ID = os.environ.get("SEARCH_ENGINE_ID")

# Load Keys
google_keys_str = os.environ.get("GOOGLE_KEYS", "")
GOOGLE_KEYS_LIST = [k.strip() for k in google_keys_str.split(',') if k.strip()]

groq_keys_str = os.environ.get("GROQ_KEYS", "")
GROQ_KEYS_LIST = [k.strip() for k in groq_keys_str.split(',') if k.strip()]

print(f"Server Ready: {len(GOOGLE_KEYS_LIST)} Google Keys, {len(GROQ_KEYS_LIST)} Groq Keys.")

# --- 1. AI KEYWORD EXTRACTOR (STRICT MODE ⚡) ---
def extract_legal_keyword(user_query):
    system_prompt = """
    You are a Legal Search Keyword Extractor.
    
    YOUR ONLY GOAL:
    Convert the user's query into the MOST SPECIFIC Indian Law Act and Section number.
    
    STRICT RULES:
    1. Output MUST be ONLY the Act Name and Section Number (e.g., "IPC Section 302").
    2. Do NOT output full sentences.
    3. Do NOT output the user's question.
    4. If the user asks in Tamil/Hindi, translate the legal intent to ENGLISH Act/Section.
    5. If it is a greeting (Hi, Hello) or non-legal, output: "NO_LAW".
    
    EXAMPLES:
    User: "திருட்டுக்கு என்ன தண்டனை?"
    Output: IPC Section 379
    
    User: "What is punishment for murder?"
    Output: IPC Section 302
    
    User: "Cheating case details"
    Output: IPC Section 420
    
    User: "Hi how are you"
    Output: NO_LAW
    """
    
    for api_key in GROQ_KEYS_LIST:
        try:
            client = Groq(api_key=api_key)
            completion = client.chat.completions.create(
                model="llama-3.3-70b-versatile",
                messages=[
                    {"role": "system", "content": system_prompt},
                    {"role": "user", "content": user_query}
                ],
                temperature=0.1, # Extremely low for precision
                max_tokens=20    # Limit strict to short output
            )
            keyword = completion.choices[0].message.content.strip()
            
            # Clean up: Remove any extra punctuation or quotes
            keyword = keyword.replace('"', '').replace("'", "").strip()
            
            print(f"🔍 AI Extracted Keyword: {keyword}") # Check Replit Console log
            
            if "NO_LAW" in keyword: return "NO_LAW"
            return keyword
        except:
            continue
            
    return "NO_LAW" 

# --- 2. GET EXACT LINKS (Using Short Keyword) ---
def get_legal_links(search_term):
    if search_term == "NO_LAW" or not search_term:
        return None 

    links = {
        "India Code": "",
        "Indian Kanoon": "",
        "Devgan.in": ""
    }
    
    # Now we search ONLY using the short keyword (e.g., "IPC Section 379")
    # Adding 'Act' or 'Code' helps get better results
    search_query = f"{search_term} site:indiacode.nic.in OR site:indiankanoon.org OR site:devgan.in"
    url = "https://www.googleapis.com/customsearch/v1"
    
    data = {}
    
    if GOOGLE_KEYS_LIST:
        for api_key in GOOGLE_KEYS_LIST:
            try:
                params = {'key': api_key, 'cx': SEARCH_ENGINE_ID, 'q': search_query, 'num': 10}
                response = requests.get(url, params=params)
                if response.status_code == 200:
                    data = response.json()
                    break
            except:
                continue

    if 'items' in data:
        for item in data['items']:
            link = item['link']
            if "indiacode.nic.in" in link and links["India Code"] == "":
                links["India Code"] = link
            elif "indiankanoon.org" in link and links["Indian Kanoon"] == "":
                links["Indian Kanoon"] = link
            elif "devgan.in" in link and links["Devgan.in"] == "":
                links["Devgan.in"] = link
    
    # Safe Fallback to Google Search (Clean URL)
    if links["India Code"] == "": links["India Code"] = f"https://www.google.com/search?q={search_term}+site:indiacode.nic.in"
    if links["Indian Kanoon"] == "": links["Indian Kanoon"] = f"https://www.google.com/search?q={search_term}+site:indiankanoon.org"
    if links["Devgan.in"] == "": links["Devgan.in"] = f"https://www.google.com/search?q={search_term}+site:devgan.in"

    return links

# --- 3. GET DETAILED ANSWER ---
def get_detailed_answer(user_query):
    system_prompt = """
    You are 'Tamil Needhi AI', a professional Indian Legal Expert if users ask what is your name.
    
    INSTRUCTIONS:
    1. DETECT LANGUAGE: Reply ONLY in the user's language.
    2. DIRECT ANSWER: No greetings (Hi, Vanakkam). Start with the law immediately.
    3. ACCURACY: Mention relevant IPC/BNS sections clearly.
    4. LEGAL ONLY: Reject non-legal questions politely.
    """
    
    for api_key in GROQ_KEYS_LIST:
        try:
            client = Groq(api_key=api_key)
            completion = client.chat.completions.create(
                model="llama-3.3-70b-versatile",
                messages=[
                    {"role": "system", "content": system_prompt},
                    {"role": "user", "content": user_query}
                ],
                temperature=0.5,
                max_tokens=4000
            )
            return completion.choices[0].message.content
        except:
            continue
    return "Server Busy."

@app.route('/')
def home():
    return "Tamil Needhi AI Server is Running... 🚀"

@app.route('/ask', methods=['POST'])
def ask_lawyer():
    try:
        data = request.json
        user_question = data.get('question')
        
        if not user_question:
            return jsonify({"answer": "கேள்வி இல்லை."}), 400

        # 1. Get Answer
        ai_response = get_detailed_answer(user_question)
        
        # 2. Extract Keyword (Strict IPC/Act Section)
        legal_keyword = extract_legal_keyword(user_question)
        
        # 3. Get Links (Uses only the short keyword)
        legal_links = get_legal_links(legal_keyword)

        response_data = {
            "answer": ai_response
        }
        
        if legal_links:
            response_data["links"] = legal_links

        return jsonify(response_data)
    
    except Exception as e:
        print(f"Error: {e}") 
        return jsonify({"answer": "Server Error."}), 500

if __name__ == '__main__':
    app.run(host='0.0.0.0', port=8080)