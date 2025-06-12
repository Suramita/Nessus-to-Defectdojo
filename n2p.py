import time
import io
import sys
import logging
import datetime
import requests
from tenable.nessus import Nessus
import urllib3

# Suppress SSL warnings
urllib3.disable_warnings(urllib3.exceptions.InsecureRequestWarning)

# Configure logging
logging.basicConfig(
    filename='/var/log/nessus_to_defectdojo.log',
    level=logging.INFO,
    format='%(asctime)s [%(levelname)s] %(message)s'
)

# Configuration
NESSUS_URL = 'https://172.18.5.46:8834'
NESSUS_ACCESS_KEY = 'a58ef06c69d018353032d8f78a75cac12c9dc72196da24fd0b655247756af79b'
NESSUS_SECRET_KEY = 'ee494cff95ea1303eb15482d60e7a8550d556aa174412f0efc3a5812d6bede45'

DEFECTDOJO_HOST = 'http://172.18.5.55:8080'
DEFECTDOJO_API_KEY = '9686a135dc98c1a3310d67952ef52d3e47347dbc'

PRODUCT_ID = 1  # Change this to your actual product ID
ENGAGEMENT_TYPE = "CI/CD"  # Or 'Interactive', 'Checkup', etc.
STATUS = "In Progress"

HEADERS = {'Authorization': f'Token {DEFECTDOJO_API_KEY}'}

# Connect to Nessus
try:
    nessus = Nessus(url=NESSUS_URL, access_key=NESSUS_ACCESS_KEY, secret_key=NESSUS_SECRET_KEY, verify=False)
    logging.info("Connected to Nessus successfully.")
except Exception as e:
    logging.error(f"Failed to connect to Nessus: {e}")
    sys.exit(1)

def get_or_create_engagement(scan_name, scan_date):
    engagement_name = f"{scan_name} - {scan_date}"
    try:
        response = requests.get(f"{DEFECTDOJO_HOST}/api/v2/engagements/?name={engagement_name}", headers=HEADERS, verify=False)
        if response.status_code == 200:
            results = response.json().get("results", [])
            if results:
                return results[0]["id"]

        # Engagement not found, create one
        start_end_date = scan_date
        engagement_data = {
            "name": engagement_name,
            "product": PRODUCT_ID,
            "target_start": start_end_date,
            "target_end": start_end_date,
            "engagement_type": ENGAGEMENT_TYPE,
            "status": STATUS,
            "active": True
        }
        create_resp = requests.post(f"{DEFECTDOJO_HOST}/api/v2/engagements/", headers=HEADERS, json=engagement_data, verify=False)
        if create_resp.status_code == 201:
            engagement_id = create_resp.json().get("id")
            logging.info(f"🆕 Created new engagement '{engagement_name}' (ID: {engagement_id})")
            return engagement_id
        else:
            logging.error(f"❌ Failed to create engagement: {create_resp.status_code} {create_resp.text}")
            return None
    except Exception as e:
        logging.error(f"❌ Error creating/getting engagement: {e}")
        return None

def scan_already_imported(scan_id):
    try:
        url = f"{DEFECTDOJO_HOST}/api/v2/tests/?test_title=Automated Nessus Import - Scan ID {scan_id}"
        response = requests.get(url, headers=HEADERS, verify=False)
        return response.status_code == 200 and response.json().get('count', 0) > 0
    except Exception as e:
        logging.error(f"Error checking if scan already imported: {e}")
        return False

def run_sync():
    try:
        scans = nessus.scans.list()['scans']
        for scan in scans:
            scan_id = scan.get('id')
            scan_name = scan.get('name', f"Scan-{scan_id}")
            scan_date = datetime.datetime.now(datetime.timezone.utc).date().isoformat()

            if scan_already_imported(scan_id):
                logging.info(f"⏭️ Scan ID {scan_id} already imported. Skipping.")
                continue

            engagement_id = get_or_create_engagement(scan_name, scan_date)
            if not engagement_id:
                logging.warning(f"⚠️ Cannot continue without engagement for scan '{scan_name}'.")
                continue

            logging.info(f"📥 Exporting scan ID {scan_id} ({scan_name})")
            scan_stream = io.BytesIO()
            try:
                scan_stream = nessus.scans.export_scan(scan_id=scan_id, format='nessus', fobj=scan_stream)
                scan_stream.seek(0)
            except Exception as e:
                logging.error(f"❌ Failed to export scan {scan_id}: {e}")
                continue

            try:
                files = {'file': (f'scan_{scan_id}.nessus', scan_stream, 'application/xml')}
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

                response = requests.post(f"{DEFECTDOJO_HOST}/api/v2/import-scan/", headers=HEADERS, files=files, data=data, verify=False)
                if response.status_code == 201:
                    logging.info(f"✅ Successfully imported scan ID {scan_id} into engagement ID {engagement_id}.")
                else:
                    logging.error(f"❌ Failed to import scan {scan_id}. Status {response.status_code}: {response.text}")

            except Exception as e:
                logging.error(f"❌ Error during scan import for scan ID {scan_id}: {e}")

    except Exception as e:
        logging.error(f"❌ General error during sync: {e}")

def main_loop():
    while True:
        logging.info("🔁 Starting sync loop...")
        run_sync()
        logging.info("😴 Sleeping for 10 minutes...")
        time.sleep(600)  # 10 minutes

if __name__ == '__main__':
    main_loop()
