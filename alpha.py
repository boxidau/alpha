#!/usr/bin/env python
import os
import boto3
import json
import shutil
import base64
import hashlib
from botocore.exceptions import ClientError

class Alpha(object):

    def __init__(self):
        self.lbd = boto3.client('lambda', 'us-east-1')
        self.iam = boto3.client('iam', 'us-east-1')
        self.lbd_fn_list = self.lbd.list_functions()

    def enumerate_modules(self, project_path):
        project_modules = {}
        for dirname in os.listdir(project_path):
            try:
                with open('%s/%s/lambda.json' % (project_path, dirname)) as lbd_config_file:
                    lbd_config = json.load(lbd_config_file)
                project_modules['%s/%s' % (project_path, dirname)] = lbd_config
            except IOError:
                #print ('Skipping %s, failed to open lambda.json' % dirname)
                pass
            except ValueError:
                print ('Could not read json from %s' % lbd_config_file)
        return project_modules

    def push_single(self, module_path):
        try:
            lbd_config_file = open('%s/lambda.json' % module_path)
            lbd_config = json.load(lbd_config_file)
            self.upload_lambda('%s' % module_path, lbd_config)

        except IOError:
            print ('Skipping %s, failed to open lambda.json' % module_path)
            pass
        except ValueError:
            print ('Could not read json from %s/lambda.json' % module_path)

    def push_all(self, project_path):
        modules = self.enumerate_modules(project_path)
        for module_path, module_config in modules.iteritems():
            self.upload_lambda(module_path, module_config)

    def promote_all(self, project_path, alias):
        modules = self.enumerate_modules(project_path)
        for module_path, module_config in modules.iteritems():
            self.promote_lambda(module_path, module_config, alias)

    def upload_lambda(self, dirname, lbd_config):
        tmp_dir = '/tmp/python-%s' % os.getpid()
        archive = shutil.make_archive(
            '%s/%s' % (tmp_dir, lbd_config['name']),
            'zip',
            '%s/src' % dirname,
            '.'
        )

        archive_file = open(archive, "rb")
        policy_name='alpha_policy_lambda_%s' % lbd_config['name']


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

            fn_role = self.iam.create_role(
                RoleName='alpha_role_lambda_%s' % lbd_config['name'],
                AssumeRolePolicyDocument=json.dumps(lambda_assume_role_policy)
            )

            fn_policy = self.iam.put_role_policy(
                RoleName='alpha_role_lambda_%s' % lbd_config['name'],
                PolicyName=policy_name,
                PolicyDocument=json.dumps(lbd_config['policy'])
            )

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
                print('New function code detected for %s' % lbd_config['name'])

                self.lbd.update_function_code(
                    FunctionName=lbd_config['name'],
                    ZipFile=archive_file_content,
                    Publish=True
                )
                # update function code
            else:
                # code already current
                print('Lambda code up-to-date for %s' % lbd_config['name'])

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
                print('Lambda config up-to-date for %s' % lbd_config['name'])
            else:
                print('Updating function config for %s' % lbd_config['name'])
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
                print('Updating policy for %s' % lbd_config['name'])
                fn_policy = self.iam.put_role_policy(
                    RoleName=role_name,
                    PolicyName=policy_name,
                    PolicyDocument=json.dumps(lbd_config['policy'])
                )
            else:
                print('Policy up-to-date for %s' % lbd_config['name'])

    def promote_lambda(self, module_path, module_config, alias):
        # promotes an aliased version to a resolved version of $LATEST
        existing_fn = next((fn for fn in self.lbd_fn_list['Functions'] if fn['FunctionName'] == module_config['name']), None)
        if not existing_fn:
            raise ValueError('Lambda function %s does not exist on AWS and thus cannot be promoted' % module_config['name'])

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
                print('Alias %s for %s is up-to-date' % (alias, module_config['name']))
            else:
                print('Updating alias %s for %s to version %s' % (alias, module_config['name'], latest_version))
                self.lbd.update_alias(
                    FunctionName=module_config['name'],
                    Name=alias,
                    FunctionVersion=latest_version
                )
        else:
            print('Creating alias %s for %s at version %s' % (alias, module_config['name'], latest_version))
            self.lbd.create_alias(
                FunctionName=module_config['name'],
                Name=alias,
                FunctionVersion=latest_version
            )