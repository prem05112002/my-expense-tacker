from parser import HDFCParser
import json

test_cases = [
    {
        "id": "1",
        "subject": "❗  You have done a UPI txn. Check details!",
        "body": "HDFC BANK Dear Customer, Rs.1115.00 has been debited from account 8444 to VPA gpay-11259170531@okbizaxis GRAJ PROTENS on 18-01-26. Your UPI transaction reference number is 117354235630."
    },
    {
        "id": "2",
        "subject": "View: Account update for your HDFC Bank A/c",
        "body": "HDFC BANK Dear Customer, Rs. 4000.00 is successfully credited to your account **8444 by VPA mavnathan175@okaxis VENKATANATHAN on 10-01-26. Your UPI transaction reference number is 601051708634."
    },
    {
        "id": "3",
        "subject": "Rs.2.00 debited via Debit Card **5948",
        "body": "HDFC BANK Dear Customer, Greetings from HDFC Bank! Rs.2.00 is debited from your HDFC Bank Debit Card ending 5948 at AMAZONAWSESC on 26 Dec, 2025 at 22:57:26."
    },
    {
        "id": "4",
        "subject": "❗ New Deposit Alert: Check your A/c balance now!",
        "body": "HDFC BANK Dear Customer, You have received a credit in your account. Here are the details The amount credited/received is INR 1,11,163.00 in your account XX8444 on 25-JUL-2025 on account of NEFT Cr-CITI0100000-CITICORP SERVICES INDIA PVT LTD-HR-PREMKUMARAN S-CITIN52025072598253074 Your A/c is at HDFC"
    }
]

parser = HDFCParser()

print(f"{'='*60}")
print(f"  {'FULL DB EXTRACTION REPORT':^56}")
print(f"{'='*60}\n")

for t in test_cases:
    res = parser.parse(t['body'], t['subject'])
    
    print(f"--- TRANSACTION ID: {t['id']} ---")
    if res:
        # Convert Date object to string for printing
        if res.get('date'):
            res['date'] = res['date'].strftime('%Y-%m-%d')
            
        # Print each field aligned
        for key, value in res.items():
            print(f"{key:<18}: {value}")
        print("\n" + "-"*60 + "\n")
    else:
        print("❌ FAILED TO PARSE\n")