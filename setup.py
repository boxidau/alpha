try:
    from setuptools import setup, find_packages
except ImportError:
    from distutils.core import setup

with open('requirements.txt') as f:
    required = f.read().splitlines()

setup(
    name='alpha',
    version='0.2',
    url='https://github.com/boxidau/alpha',
    author='Simon Mirco',
    description='Continuous delivery for AWS Lambda functions',
    py_modules=['alpha', 'alphacli'],
    include_package_data=True,
    install_requires=required,
    entry_points='''
        [console_scripts]
        alpha=alphacli:cli
    ''',
)