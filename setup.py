from setuptools import setup

setup(
    name='alpha-lambda',
    version='0.1',
    py_modules=['alphacli'],
    include_package_data=True,
    install_requires=[
        'click'
    ],
    entry_points='''
        [console_scripts]
        alpha=alphacli:cli
    ''',
)