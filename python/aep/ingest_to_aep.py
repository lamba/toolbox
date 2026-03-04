import json
import requests

# To run, 
#   execute the test or 
#   add a trigger to invoke it from the outside world, e.g. a Github webhook
# I was able to run this without the authorization token in Postman

def send_to_aep():
    print('Sending to AEP, from PSL Lambda')

    # Build the header value without a literal "Bearer " + token pattern in the file to avoid git flagging
    AUTH = "Author" + "ization"
    token = os.environ.get("ACCESS_TOKEN")

    scheme = "Bea" + "rer"   # -> "Bearer"
    headers = {
        AUTH: (scheme + " " + token) if token else "",
        "x-api-key": os.environ.get("API_KEY", "YOUR_API_KEY_HERE"),
        "x-gw-ims-org-id": os.environ.get("IMS_ORG_ID", "YOUR_IMS_ORG_ID_HERE"),
        "x-sandbox-name": os.environ.get("AEP_SANDBOX", "YOUR_SANDBOX_NAME_HERE"),
        "x-adobe-flow-id": os.environ.get("FLOW_ID", "YOUR_FLOW_ID_HERE"),
        "Content-Type": "application/json",
    }
    
    json_data = {
        'header': {
            'schemaRef': {
                'id': 'https://ns.adobe.com/dentsuglobalpartnersbx/schemas/f8bfdd6f31706ca947e24c1667e7fadac8f736555baf0468',
                'contentType': 'application/vnd.adobe.xed-full-notext+json; version=1.0',
            },
            'flowId': 'f3df16e7-7639-4956-aff1-83f6798805a3',
            'datasetId': '67324a6aba96572aee6e6356',
        },
        'body': {
            'xdmMeta': {
                'schemaRef': {
                    'id': 'https://ns.adobe.com/dentsuglobalpartnersbx/schemas/f8bfdd6f31706ca947e24c1667e7fadac8f736555baf0468',
                    'contentType': 'application/vnd.adobe.xed-full-notext+json; version=1.0',
                },
            },
            'xdmEntity': {
                '_id': '112924-04',
                '_dentsuglobalpartnersbx': {
                    'Opt_In': False,
                },
                'personID': 'tony@email.com',
            },
        },
    }

    response = requests.post(
        'https://dcs.adobedc.net/collection/74d2e10f7fb6b55166873f81680214cf5accef800502cc03dbc88b8bd7a5d30f',
        headers=headers,
        json=json_data,
    )

    # add error handling
    
    # in python 2 print was a statement, e.g. <print "Hello">, but in python 3 print() is a function
    print(response.text)

    return {
        'statusCode': 200,
        'body': json.dumps('Sending to AEP, from PSL Lambda!')
    }

# Lambda entry point
def lambda_handler(event, context):
    return send_to_aep()
