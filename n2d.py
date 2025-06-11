mport requests
import os

# === CONFIGURATION ===
DEFECTDOJO_HOST = "http://localhost:8080"  # Change to your DefectDojo host
API_KEY = "your_defectdojo_api_key"        # Get this from DefectDojo > API Key
NESSUS_FILE_PATH = "/path/to/your/report.nessus"  # Full path to the Nessus report file
TEST_TITLE = "Automated Nessus Import"
ENGAGEMENT_ID = 1                          # Existing engagement ID in DefectDojo
SCAN_TYPE = "Nessus Scan"                 # Valid scan types in DefectDojo
PRODUCT_TYPE = 1                          # Optional if auto-created
PRODUCT_ID = 1                            # Optional if auto-created
ENGAGEMENT_NAME = "Nessus Scan Engagement"

# === HEADERS ===
headers = {
            'Authorization': f'Token {API_KEY}'
            }

# === FILE PAYLOAD ===
files = {
            'file': open(NESSUS_FILE_PATH, 'rb')
            }

# === DATA PAYLOAD ===
data = {
            'scan_type': SCAN_TYPE,
                'engagement': ENGAGEMENT_ID,
                    'minimum_severity': 'Low',
                        'active': 'true',
                            'verified': 'true',
                                'scan_date': '2025-06-11',
                                    'test_title': TEST_TITLE,
                                        'close_old_findings': 'false',
                                            'skip_duplicates': 'true'
                                            }

# === API CALL ===
upload_url = f"{DEFECTDOJO_HOST}/api/v2/import-scan/"

response = requests.post(upload_url, headers=headers, files=files, data=data)

# === OUTPUT RESULT ===
if response.status_code == 201:
        print("Nessus report uploaded successfully to DefectDojo.")
    else:
            print(f"Failed to upload report. Status: {response.status_code}")
                print(response.text)

