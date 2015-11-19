import pytest
from alpha import Alpha
import tempfile
import shutil
import os
import json
from datetime import datetime
import boto3

test_config = {
  "name": "test-lambda",
  "description": "Test 123",
  "runtime": "python2.7",
  "handler": "test.lambda_handler",
  "memory": 128,
  "timeout": 5,
  "policy": {
    "Version": "2012-10-17",
    "Statement": [
      {
        "Resource": "*",
        "Action": [
          "logs:CreateLogGroup",
          "logs:CreateLogStream",
          "logs:PutLogEvents"
        ],
        "Effect": "Allow"
      }
    ]
  }
}

broken_config = {
  "name": "test-lambda",
  "description": "Test 123",
  "runtime": "python2.7",
  "timeout": 5,
  "policy": {
    "Version": "2012-10-17",
    "Statement": [
      {
        "Resource": "*",
        "Action": [
          "logs:CreateLogGroup",
          "logs:CreateLogStream",
          "logs:PutLogEvents"
        ],
        "Effect": "Allow"
      }
    ]
  }
}


@pytest.yield_fixture()
def create_file_structure_src():
    tempdir = tempfile.mkdtemp(prefix='alpha_test')
    os.makedirs(os.path.join(tempdir, 'test-lambda'))
    os.makedirs(os.path.join(tempdir, 'test-lambda', 'src'))
    with open(os.path.join(tempdir, 'test-lambda', 'lambda.json'), 'w') as f:
        f.writelines(json.dumps(test_config))

    open(os.path.join(tempdir, 'test-lambda', 'src', 'test.py'), 'w').close()

    yield tempdir

    shutil.rmtree(tempdir)

@pytest.yield_fixture()
def create_broken_file_structure_src():
    tempdir = tempfile.mkdtemp(prefix='alpha_test')
    os.makedirs(os.path.join(tempdir, 'test-lambda'))
    os.makedirs(os.path.join(tempdir, 'test-lambda', 'src'))
    with open(os.path.join(tempdir, 'test-lambda', 'lambda.json'), 'w') as f:
        f.writelines(json.dumps(broken_config))

    open(os.path.join(tempdir, 'test-lambda', 'src', 'test.py'), 'w').close()

    yield tempdir

    shutil.rmtree(tempdir)

@pytest.yield_fixture(scope='session')
def alpha():
    yield Alpha()

@pytest.yield_fixture()
def remove_network_alpha(alpha, monkeypatch, request, mocker):

    lambda_list = {'Functions':[]}
    new_role = {
    'Role': {
        'Path': '/',
        'RoleName': 'alpha_role_lambda_test-lambda',
        'RoleId': 'string',
        'Arn': 'arn:aws:iam::12345678910:role/alpha_role_lambda_test-lambda',
        'CreateDate': datetime(2015, 1, 1),
    }}

    new_function = {
    'FunctionName': 'test-lambda',
    'FunctionArn': 'arn:aws:lambda:ap-northeast-1:12345678910:function:test-lambda2',
    'Runtime': 'python2.7',
    'Role': 'alpha_role_lambda_test-lambda',
    'Handler': 'test.lambda_handler',
    'CodeSize': 256,
    'Description': 'Test 123',
    'Timeout': 5,
    'MemorySize': 128,
    'LastModified': datetime(2015, 10, 10),
    'CodeSha256': '3ab7f19e8d880de68773acdd02451260062075fa23e2b34eff02b752b170920f',
    'Version': '1'
    }

    mock_aws = mocker.Mock()
    mock_aws.create_role.return_value = new_role
    mock_aws.put_role_policy.return_value = None
    mock_aws.list_functions.return_value = lambda_list
    mock_aws.create_function.return_value = new_function

    mocker.patch.object(alpha, 'iam', new=mock_aws)
    mocker.patch.object(alpha, 'lbd', new=mock_aws)

    yield alpha

