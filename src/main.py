import argparse
import json
import requests
import pathlib

from urllib.parse import urlparse
from auth import AWSSignatureV4


def create_auth():
    return AWSSignatureV4(
        region='eu-west-1',
        service='execute-api',
        aws_access_key=args.access_key_id,
        aws_secret_key=args.secret_access_key,
        aws_api_key=args.api_key
    )


def create_signing_headers(method, path, body):
    auth = create_auth()
    uri = urlparse(f'{args.api_endpoint}{path}')

    auth_headers = auth.sign_headers(
        uri=uri,
        method=method,
        body=body
    )

    headers = {**auth_headers, 'Content-Type': 'application/json'}
    return uri, headers


def post_documents():
    body = json.dumps({'contentType': args.content_type, 'consentId': args.consent_id}).encode()
    uri, headers = create_signing_headers('POST', '/documents', body)

    post_documents_response = requests.post(
        url=uri.geturl(),
        headers=headers,
        data=body, 
    timeout=60)
    post_documents_response.raise_for_status()
    return post_documents_response.json()


def put_document(presigned_url):
    body = pathlib.Path(args.document_path).read_bytes()
    headers = {'Content-Type': args.content_type}

    if args.with_s3_kms:
        headers['x-amz-server-side-encryption'] = 'aws:kms'

    put_document_response = requests.put(presigned_url, data=body, headers=headers, timeout=60)
    put_document_response.raise_for_status()
    return put_document_response.content.decode()


def post_predictions(document_id, model_name):
    body = json.dumps({'documentId': document_id, 'modelName': model_name}).encode()
    uri, headers = create_signing_headers('POST', '/predictions', body)

    post_predictions_response = requests.post(
        url=uri.geturl(),
        headers=headers,
        data=body, 
    timeout=60)
    post_predictions_response.raise_for_status()
    return post_predictions_response.json()


def upload_document():
    post_documents_response = post_documents()
    document_id = post_documents_response['documentId']
    presigned_url = post_documents_response['uploadUrl']
    put_document(presigned_url)
    return document_id


def invoice_prediction():
    document_id = upload_document()
    predictions = post_predictions(document_id, 'invoice')
    print(json.dumps(predictions, indent=2))


def receipt_prediction():
    document_id = upload_document()
    predictions = post_predictions(document_id, 'receipt')
    print(json.dumps(predictions, indent=2))


def document_split():
    document_id = upload_document()
    predictions = post_predictions(document_id, 'documentSplit')
    print(json.dumps(predictions, indent=2))


if __name__ == '__main__':
    parser = argparse.ArgumentParser()
    parser.add_argument('api_endpoint', help='HTTPS endpoint for REST API')
    parser.add_argument('api_key')
    parser.add_argument('access_key_id')
    parser.add_argument('secret_access_key')
    parser.add_argument('--with_s3_kms', action='store_true')
    subparsers = parser.add_subparsers()

    invoice_prediction_parser = subparsers.add_parser('invoice_prediction')
    invoice_prediction_parser.add_argument('document_path', help='Path to document to make predictions on')
    invoice_prediction_parser.add_argument('content_type', choices={'image/jpeg', 'application/pdf'},
                                           help='Content-Type of document to make predictions on')
    invoice_prediction_parser.add_argument('--consent_id', default='1234',
                                           help='Consent ID is typically a mapping from end user to a unique identifier')
    invoice_prediction_parser.set_defaults(cmd=invoice_prediction)

    receipt_prediction_parser = subparsers.add_parser('receipt_prediction')
    receipt_prediction_parser.add_argument('document_path', help='Path to document to make predictions on')
    receipt_prediction_parser.add_argument('content_type', choices={'image/jpeg', 'application/pdf'},
                                           help='Content-Type of document to make predictions on')
    receipt_prediction_parser.add_argument('--consent_id', default='1234',
                                           help='Consent ID is typically a mapping from end user to a unique identifier')
    receipt_prediction_parser.set_defaults(cmd=receipt_prediction)

    document_split_parser = subparsers.add_parser('document_split')
    document_split_parser.add_argument('document_path', help='Path to document to split')
    document_split_parser.add_argument('content_type', choices={'application/pdf'},
                                       help='Content-Type of document to split')
    document_split_parser.add_argument('--consent_id', default='1234',
                                       help='Consent ID is typically a mapping from end user to a unique identifier')
    document_split_parser.set_defaults(cmd=document_split)

    args = parser.parse_args()
    args.cmd()
