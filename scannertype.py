import requests

DEFECTDOJO_URL = 'http://172.18.5.55:8080'
API_KEY = '9686a135dc98c1a3310d67952ef52d3e47347dbc'

headers = {
    'Authorization': f'Token {API_KEY}',
    'accept': 'application/json',
}

response = requests.post(f'{DEFECTDOJO_URL}/v2/product_api_scan_configurations', headers=headers)

print(f"Status code: {response.status_code}")
print(response.text)
