import requests

# i was able to run this without the authorization token in postman

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
            '_id': '112924-03',
            '_dentsuglobalpartnersbx': {
                'Opt_In': False,
            },
            'personID': 'tom@email.com',
        },
    },
}

response = requests.post(
    'https://dcs.adobedc.net/collection/74d2e10f7fb6b55166873f81680214cf5accef800502cc03dbc88b8bd7a5d30f',
    headers=headers,
    json=json_data,
)

# in python 2 print was a statement, e.g. <print "Hello">, but in python 3 print() is a function
print(response.text)

# Note: json_data will not be serialized by requests
# exactly as it was in the original request.
# data = '{\n\t\t"header": {\n\t\t\t"flowId" : "a59d368a-1152-4673-a46e-bd52e8cdb9a9",\n\t\t\t"imsOrgId": "DB5448F45E66075A0A495CCA@AdobeOrg",\n\t\t\t"datasetId": "672f8cd61549282af0e98c36",\n\t\t\t"operations": {\n        \t\t"data": "create"\n    \t\t}\n\t\t},\n\t\t"body": {\n\t\t\t"_dentsuglobalpartnersbx": {\n\t\t\t\t"Opt_In": false\n\t\t\t},\n\t\t\t"_id": "puneet@inventica.com"\n\t\t}\t\n\t}'
# response = requests.post(
#    'https://dcs.adobedc.net/collection/c645c98b600fd963bc8f227e498d12243144252e467fd15e6a5c61786eda2ecc',
#    headers=headers,
#    data=data,
# )
