import time
import io
import sys
import datetime
import urllib3
from tenable.nessus import Nessus
import requests

# Suppress self-signed SSL warnings
urllib3.disable_warnings(urllib3.exceptions.InsecureRequestWarning)

# --- CONFIGURATION ---
NESSUS_URL = 'https://172.18.5.46:8834'
NESSUS_ACCESS_KEY = 'a58ef06c69d018353032d8f78a75cac12c9dc72196da24fd0b655247756af79b'
NESSUS_SECRET_KEY = 'ee494cff95ea1303eb15482d60e7a8550d556aa174412f0efc3a5812d6bede45'

DEFECTDOJO_HOST = 'http://172.18.5.55:8080'
DEFECTDOJO_API_KEY = '9686a135dc98c1a3310d67952ef52d3e47347dbc'

headers = {'Authorization': f'Token {DEFECTDOJO_API_KEY}'}

# --- CONNECT TO NESSUS ---
try:
    nessus = Nessus(url=NESSUS_URL, access_key=NESSUS_ACCESS_KEY, secret_key=NESSUS_SECRET_KEY, verify=False)
    print("✅ Connected to Nessus.")
except Exception as e:
    print(f"❌ Failed to connect to Nessus: {e}")
    sys.exit(1)


# --- FUNCTIONS ---

def get_engagements():
    """Fetch all engagements."""
    url = f"{DEFECTDOJO_HOST}/api/v2/engagements/?limit=1000"
    try:
        response = requests.get(url, headers=headers, verify=False)
        response.raise_for_status()
        return response.json().get('results', [])
    except Exception as e:
        print(f"❌ Error fetching engagements: {e}")
        return []


def get_tests_for_engagement(engagement_id):
    """Fetch tests for a given engagement ID."""
    url = f"{DEFECTDOJO_HOST}/api/v2/tests/?engagement={engagement_id}&limit=1000"
    try:
        response = requests.get(url, headers=headers, verify=False)
        response.raise_for_status()
        return response.json().get('results', [])
    except Exception as e:
        print(f"❌ Error fetching tests for engagement {engagement_id}: {e}")
        return []


def has_been_imported(scan_id, engagement_id):
    """Check if a scan with this scan_id was already imported based on the test title."""
    tests = get_tests_for_engagement(engagement_id)
    title = f'Automated Nessus Import - Scan ID {scan_id}'
    return any(test['title'] == title for test in tests)


def get_scan_data(scan_id):
    """Export Nessus scan and return its data stream."""
    buffer = io.BytesIO()
    try:
        buffer = nessus.scans.export_scan(scan_id=scan_id, format='nessus', fobj=buffer)
        buffer.seek(0)
        return buffer
    except Exception as e:
        print(f"❌ Failed to export scan {scan_id}: {e}")
        return None


def send_to_defectdojo(scan_id, scan_name, engagement_id, file_stream):
    """Send the Nessus scan to DefectDojo."""
    try:
        scan_date = datetime.datetime.now(datetime.timezone.utc).date().isoformat()
        files = {'file': (f'scan_{scan_id}.nessus', file_stream, 'application/xml')}
        data = {
            'scan_type': 'Tenable Scan',
            'engagement': engagement_id,
            'minimum_severity': 'Low',
            'active': 'true',
            'verified': 'true',
            'scan_date': scan_date,
            'test_title': f'Automated Nessus Import - Scan ID {scan_id}',
            'close_old_findings': 'false',
            'skip_duplicates': 'true'
        }

        response = requests.post(
            f'{DEFECTDOJO_HOST}/api/v2/import-scan/',
            headers=headers,
            files=files,
            data=data,
            verify=False
        )

        if response.status_code == 201:
            print(f"✅ Scan ID {scan_id} successfully imported into engagement ID {engagement_id}.")
        else:
            print(f"❌ Failed to import scan {scan_id}. Status: {response.status_code}. Response: {response.text}")
    except Exception as e:
        print(f"❌ Error sending scan {scan_id} to DefectDojo: {e}")


# --- MAIN PROCESSING LOOP ---

print("🔄 Starting scan export and import loop...")
engagements = get_engagements()

try:
    scans = nessus.scans.list()['scans']
    for scan in scans:
        if 'last_modification_date' not in scan:
            continue

        scan_id = scan['id']
        scan_name = scan.get('name', '').lower()

        # Try to find matching engagement
        matching_engagement = next((e for e in engagements if scan_name in e['name'].lower()), None)
        if not matching_engagement:
            print(f"⏭️ Skipping scan '{scan_name}' — no matching engagement.")
            continue

        engagement_id = matching_engagement['id']

        # Check if already imported
        if has_been_imported(scan_id, engagement_id):
            print(f"🛑 Scan ID {scan_id} already imported. Skipping.")
            continue

        # Export scan
        print(f"📦 Exporting scan ID {scan_id} ('{scan_name}')...")
        data_stream = get_scan_data(scan_id)
        if not data_stream:
            continue

        # Send to DefectDojo
        send_to_defectdojo(scan_id, scan_name, engagement_id, data_stream)

except Exception as e:
    print(f"❌ Unexpected error during main loop: {e}")
    sys.exit(1)
