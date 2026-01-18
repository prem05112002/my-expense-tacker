import re

INPUT_FILE = "email_samples.txt"
OUTPUT_FILE = "unique_subjects_strict.txt"

def get_strict_key(text):
    """
    Removes ALL spaces and converts to lowercase for comparison.
    Example: "Alert:  UPI Transaction" -> "alert:upitransaction"
    """
    if not text:
        return ""
    # Remove all whitespace characters entirely
    return "".join(text.split()).lower()

def extract_strict_unique_subjects():
    try:
        print(f"📂 Reading {INPUT_FILE}...")
        
        with open(INPUT_FILE, "r", encoding="utf-8") as f:
            content = f.read()

        # Split file by the separator
        raw_samples = content.split("==================================================")
        
        # Dictionary to store unique subjects: Key = Strict String, Value = Readable String
        unique_map = {}
        total_found = 0

        for raw in raw_samples:
            lines = raw.strip().split("\n")
            original_subject = None
            
            # Extract Subject Line
            for line in lines:
                if line.startswith("SUBJECT:"):
                    original_subject = line.replace("SUBJECT:", "").strip()
                    break
            
            if original_subject:
                total_found += 1
                
                # Create Strict Key (No spaces, lowercase)
                strict_key = get_strict_key(original_subject)
                
                # Only add if this strict key hasn't been seen
                if strict_key not in unique_map:
                    # We store the original readable version to write to the file later
                    # (We clean up excessive spaces just for readability in the output)
                    readable_version = " ".join(original_subject.split())
                    unique_map[strict_key] = readable_version

        print(f"   Found {total_found} total subjects.")
        print(f"✨ Identified {len(unique_map)} strictly unique subjects.")

        # Save to new file
        with open(OUTPUT_FILE, "w", encoding="utf-8") as f:
            for i, (key, subject) in enumerate(unique_map.items()):
                f.write(f"{i+1}. {subject}\n")

        print(f"✅ Saved clean list to '{OUTPUT_FILE}'")

    except FileNotFoundError:
        print(f"❌ Error: Could not find '{INPUT_FILE}'.")

if __name__ == "__main__":
    extract_strict_unique_subjects()