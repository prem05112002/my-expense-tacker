import json
import os
import time
from datetime import datetime
from groq import Groq
from bs4 import BeautifulSoup
# 👇 REMOVED: LLM_BACKEND and OLLAMA_URL imports
from config import GROQ_API_KEY, CATEGORY_LIST

class HybridParser:
    def __init__(self):
        # 🚀 STRICT MODE: GROQ ONLY
        api_key = GROQ_API_KEY or os.getenv('GROQ_API_KEY')
        if not api_key:
            raise ValueError("❌ CRITICAL: GROQ_API_KEY is missing")
        self.groq_client = Groq(api_key=api_key)
        print("🚀 LLM Backend: GROQ (Optimized)")

    def _clean_html(self, html_content):
        if not html_content: return ""
        soup = BeautifulSoup(html_content, "html.parser")
        text = soup.get_text(separator=" ", strip=True)
        return " ".join(text.split())

    def _clean_merchant_name(self, merchant_raw):
        if not merchant_raw: return "Unknown"
        merchant_raw = merchant_raw.replace('Info:', '').replace('UPI-', '').strip()
        if '@' in merchant_raw:
            handle = merchant_raw.split('@')[0]
            clean_name = handle.replace('.', ' ').replace('_', ' ')
            return clean_name.title()
        return merchant_raw.title()

    # Backup helper for Ref Numbers
    def _extract_reference_number(self, body):
        import re
        patterns = [
            r'UPI Ref No\s*[:\-]?\s*(\d+)',
            r'Ref No\s*[:\-]?\s*(\d+)',
            r'RRN\s*[:\-]?\s*(\d+)',
            r'IMPS Ref\s*[:\-]?\s*(\d+)',
            r'Transaction ID\s*[:\-]?\s*(\d+)'
        ]
        for p in patterns:
            match = re.search(p, body, re.IGNORECASE)
            if match: return match.group(1)
        return None

    def _process_with_llm(self, user_id, sender, body):
        # 👇 UPDATED PROMPT: Smarter Credit Logic
        prompt = f"""
        Extract financial data from this bank email.
        
        Email Body: "{body[:2000]}"
        
        Allowed Categories: {", ".join(CATEGORY_LIST)}
        
        GOAL: Extract Amount, Merchant, Date, Ref Number, and Type.
        
        RULES:
        1. Amount: numerical only (e.g., 1050.50). If not found, return null.
        2. Type: "CREDIT" or "DEBIT".
        3. Merchant: Who is the transaction with?
        4. Ref Number: UPI Ref, RRN, Txn ID.
        
        5. CATEGORIZATION LOGIC:
           - DEBITS: Choose the best fit from Allowed Categories.
           - CREDITS: 
             * Use "Income" ONLY if keywords like 'Salary', 'Dividend', 'Interest' appear.
             * Use "Refund" if 'Refund' or 'Reversal' appears.
             * Use "Transfer" for P2P credits.
             * Otherwise, use "Uncategorized".

        Output strict JSON:
        {{
            "amount": 1050.00,
            "merchant": "Netflix",
            "date": "YYYY-MM-DD",
            "category": "Entertainment",
            "type": "DEBIT",
            "ref_number": "123456"
        }}
        """

        retries = 3
        for attempt in range(retries):
            try:
                # 🚀 DIRECT CALL (No Ollama fallback)
                response_json = self._call_groq(prompt)
                data = json.loads(response_json)
                
                # Fallback: If LLM missed Ref No, try regex helper
                if not data.get('ref_number'):
                    data['ref_number'] = self._extract_reference_number(body)
                
                return data
            
            except Exception as e:
                if "429" in str(e) or "rate limit" in str(e).lower():
                    wait_time = (2 ** attempt) * 1.5 
                    print(f"⏳ Groq Rate Limit. Retrying in {wait_time}s...")
                    time.sleep(wait_time)
                else:
                    print(f"❌ LLM Error: {e}")
                    return None
        return None

    def _call_groq(self, prompt):
        completion = self.groq_client.chat.completions.create(
            messages=[
                {"role": "system", "content": "You are a JSON-only financial parser API."},
                {"role": "user", "content": prompt}
            ],
            model="llama-3.3-70b-versatile", 
            temperature=0,
            response_format={"type": "json_object"} 
        )
        return completion.choices[0].message.content

    def parse_email(self, user_id, email_data):
        sender = email_data['sender']
        body = self._clean_html(email_data['body'])
        
        print(f"🤖 AI Scanning: {sender}...")
        return self._process_with_llm(user_id, sender, body)