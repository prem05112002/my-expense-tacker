from parser import HDFCParser

# NOTE: Spacing is chaotic to test \s* and robustness
test_cases = [
    {
        "id": "1. UPI DEBIT",
        "subject": "❗ You have done a UPI txn. Check details!",
        "body": "Rs.250.00hasbeendebited from account **1234 to VPA swiggy@okicici SWIGGY LIMITED on 18-01-2024. Your UPI transaction reference number is 112233."
    },
    {
        "id": "2. UPI CREDIT (No Merchant Name)",
        "subject": "View: Account update for your HDFC Bank A/c",
        "body": "Rs. 5,000.00 is successfullycredited to your account **1234 by VPA friend@okaxis   on 19/01/2024."
    },
    {
        "id": "3. CARD SPEND",
        "subject": "Rs.1,200.00 debited via Debit Card **4321",
        "body": "Rs.1,200.00isdebited from your Debit Card ending 4321 at AMAZON RETAIL   on 2024-01-20 at 10:30."
    },
    {
        "id": "4. DEPOSIT",
        "subject": "❗ New Deposit Alert: Check your A/c balance now!",
        "body": "The amount is INR 45,000.00 in your account on 21-01-2024 on account of NEFT TECH SOLUTIONS PVT LTD Your A/c..."
    }
]

parser = HDFCParser()

print(f"{'TYPE':<15} | {'AMOUNT':<10} | {'BANK_ID':<10} | {'MERCHANT'}")
print("-" * 60)

for test in test_cases:
    res = parser.parse(test['body'], test['subject'])
    if res:
        print(f"{res['category']:<15} | {res['amount']:<10} | {str(res['bank_id']):<10} | {res['merchant']}")
    else:
        print(f"❌ FAILED: {test['id']}")