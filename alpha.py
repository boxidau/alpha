#!/usr/bin/env python
import os
import boto3
import json
import shutil
import base64
import hashlib
import time
import tempfile
from botocore.exceptions import ClientError
from contextlib import contextmanager


class Alpha(object):

    def __init__(self):
        self.lbd = boto3.client('lambda')
        self.iam = boto3.client('iam')
        self._fn_list = None

    @property
    def lbd_fn_list(self):
        if self._fn_list is None:
            self._fn_list = self.lbd.list_functions()
        return self._fn_list

    @staticmethod
    def enumerate_modules(project_path):
        for dirname in os.listdir(project_path):
            try:
                with open(os.path.join(project_path, dirname, 'lambda.json')) as lbd_config_file:
                    yield os.path.join(project_path, dirname), json.load(lbd_config_file)
            except IOError:
                #print ('Skipping {0}, failed to open lambda.json'.format(dirname)
                pass
            except ValueError:
                print ('Could not read json from {0}'.format(lbd_config_file))

    @staticmethod
    def check_config(lbd_config):
        required_fields = {'policy', 'runtime', 'timeout', 'memory', 'name'}
        if required_fields.issubset(lbd_config.keys()):
            return True
        print('Skipping {0}, you do not have all required field in your '
              'configuration.'.format(lbd_config['name']))
        return False

    def push_single(self, module_path):
        try:
            with open(os.path.join(module_path, 'lambda.json')) as lbd_config_file:
                lbd_config = json.load(lbd_config_file)
            if self.check_config(lbd_config):
                if 'region' in lbd_config.keys():
                    self.lbd = boto3.client('lambda', region_name=lbd_config['region'])
                self.upload_lambda(module_path, lbd_config)
        except IOError:
            print ('Skipping {0}, failed to open lambda.json'.format(module_path))
            pass
        except ValueError:
            print ('Could not read json from {0}/lambda.json'.format(module_path))

    def push_all(self, project_path):
        for module_path, module_config in self.enumerate_modules(project_path):
            if self.check_config(module_config):
                if 'region' in module_config.keys():
                    self.lbd = boto3.client('lambda', region_name=module_config['region'])
                self.upload_lambda(module_path, module_config)

    def promote_all(self, project_path, alias):
        for module_path, module_config in self.enumerate_modules(project_path):
            self.promote_lambda(module_path, module_config, alias)

    def upload_lambda(self, dirname, lbd_config):
        with TemporaryDirectory() as tmp_dir:
            archive = shutil.make_archive(
                os.path.join(tmp_dir, lbd_config['name']),
                'zip',
                os.path.join(dirname, 'src'),
                '.'
            )
            archive_file = open(archive, "rb")
            policy_name='alpha_policy_lambda_{0}'.format(lbd_config['name'])
            existing_fn = next((fn for fn in self.lbd_fn_list['Functions'] if fn['FunctionName'] == lbd_config['name']), None)
            if not existing_fn:
                # New function
                lambda_assume_role_policy = {
                    "Version": "2012-10-17",
                    "Statement": [
                        {
                            "Action": "sts:AssumeRole",
                            "Effect": "Allow",
                            "Principal": {
                                "Service": "lambda.amazonaws.com"
                            }
                        }
                    ]
                }

                print('{0}: creating role'.format(lbd_config['name']))
                try:
                    fn_role = self.iam.create_role(
                        RoleName='alpha_role_lambda_{0}'.format(lbd_config['name']),
                        AssumeRolePolicyDocument=json.dumps(lambda_assume_role_policy)
                    )
                except ClientError:
                    print('{0}: warning policy might already exist'.format(lbd_config['name']))
                    fn_role = self.iam.get_role(RoleName='alpha_role_lambda_{0}'.format(lbd_config['name']))

                print('{0}: updating inline policy'.format(lbd_config['name']))
                self.iam.put_role_policy(
                    RoleName='alpha_role_lambda_{0}'.format(lbd_config['name']),
                    PolicyName=policy_name,
                    PolicyDocument=json.dumps(lbd_config['policy'])
                )

                # lambda doesn't seem to be able to assume the role without a delay here
                time.sleep(4)

                print('{0}: uploading function'.format(lbd_config['name']))
                lbd_fn_create = self.lbd.create_function(
                    FunctionName=lbd_config['name'],
                    Runtime=lbd_config['runtime'],
                    Role=fn_role['Role']['Arn'],
                    Handler=lbd_config['handler'],
                    Code={
                        'ZipFile': archive_file.read(),
                    },
                    Description=lbd_config['description'],
                    Timeout=lbd_config['timeout'],
                    MemorySize=lbd_config['memory'],
                    Publish=True
                )
            else:
                # updating existing function
                archive_file_content = archive_file.read()
                archive_hash = base64.b64encode(hashlib.sha256(archive_file_content).digest())
                if not archive_hash == existing_fn['CodeSha256']:
                    print('New function code detected for {0}'.format(lbd_config['name']))

                    self.lbd.update_function_code(
                        FunctionName=lbd_config['name'],
                        ZipFile=archive_file_content,
                        Publish=True
                    )
                    # update function code
                else:
                    # code already current
                    print('Lambda code up-to-date for {0}'.format(lbd_config['name']))

                # Check function config
                if existing_fn['Runtime'] != lbd_config['runtime']:
                    raise ValueError

                if all([
                            existing_fn['Description'] == lbd_config['description'],
                            existing_fn['Handler'] == lbd_config['handler'],
                            existing_fn['MemorySize'] == lbd_config['memory'],
                            existing_fn['Timeout'] == lbd_config['timeout']
                ]):
                    # no updates required for config
                    print('Lambda config up-to-date for {0}'.format(lbd_config['name']))
                else:
                    print('Updating function config for {0}'.format(lbd_config['name']))
                    self.lbd.update_function_configuration(
                        FunctionName=lbd_config['name'],
                        Handler=lbd_config['handler'],
                        Description=lbd_config['description'],
                        Timeout=lbd_config['timeout'],
                        MemorySize=lbd_config['memory'],
                    )

                role_name = existing_fn['Role'].split('/', 1)[1]
                fn_role_policy = self.iam.get_role_policy(RoleName=role_name, PolicyName=policy_name)

                if not fn_role_policy['PolicyDocument'] == lbd_config['policy']:
                    print('Updating policy for {0}'.format(lbd_config['name']))
                    fn_policy = self.iam.put_role_policy(
                        RoleName=role_name,
                        PolicyName=policy_name,
                        PolicyDocument=json.dumps(lbd_config['policy'])
                    )
                else:
                    print('Policy up-to-date for {0}'.format(lbd_config['name']))

    def promote_lambda(self, module_path, module_config, alias):
        # promotes an aliased version to a resolved version of $LATEST
        existing_fn = next((fn for fn in self.lbd_fn_list['Functions'] if fn['FunctionName'] == module_config['name']), None)
        if not existing_fn:
            raise ValueError('Lambda function {0} does not exist on AWS and thus cannot be promoted'.format(module_config['name']))

        try:
            existing_alias = self.lbd.get_alias(
                FunctionName=module_config['name'],
                Name=alias
            )
        except ClientError:
            pass

        versions_response = self.lbd.list_versions_by_function(FunctionName=module_config['name'])
        latest_version = versions_response['Versions'][-1]['Version']

        if existing_alias:
            if latest_version == existing_alias['FunctionVersion']:
                print('Alias {0} for {1} is up-to-date'.format(alias, module_config['name']))
            else:
                print('Updating alias {0} for {1} to version {2}'.format(alias, module_config['name'], latest_version))
                self.lbd.update_alias(
                    FunctionName=module_config['name'],
                    Name=alias,
                    FunctionVersion=latest_version
                )
        else:
            print('Creating alias {0} for {1} at version {2}'.format(alias, module_config['name'], latest_version))
            self.lbd.create_alias(
                FunctionName=module_config['name'],
                Name=alias,
                FunctionVersion=latest_version
            )


@contextmanager
def TemporaryDirectory():
    name = tempfile.mkdtemp(suffix='alpha')
    try:
        yield name
    finally:
        shutil.rmtree(name)
