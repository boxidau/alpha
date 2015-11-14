# Alpha

Alpha is a continuous deployment tool for AWS lambda. It's purpose is to make managing a project comprised of lambda functions simple.

For each function making up your project Alpha will deploy lambda configs, functions and associated roles.

Aliases are used to allow for staging environments.

## Installation
```
git clone git@github.com:boxidau/alpha.git
cd alpha
pip install .
```

After a bit more testing and possibly a name change I'll make a proper pip package

Alpha uses standard boto3 authentication methods (envvar, ~/.aws/credentials) Make sure you have this [setup](http://boto3.readthedocs.org/en/latest/guide/configuration.html).


## Project Setup

Your lambda project should have a structure like so:
```
example_project
├── test-lambda
│   ├── lambda.json
│   └── src
│       ├── index.js
│       └── required-file.js
└── test-lambda2
    ├── lambda.json
    └── src
        ├── index.js
        └── required-file.js
```

In this example test-lambda test-lambda2 are individual functions that make up a project called example_project

Each function folder must contain lambda.json and an src folder
See the example_project folder in this git repo for examples of lambda.json

## Usage

### Push

Will update/create lambda functions, configs and policies.

```
# push an entire project
# path defaults to current directory
# path should contain folders each containing lambda.json and src/
alpha push [/path/to/project]

# push a single function, config and policy
# path defaults to current directory
# path should contain lambda.json and src/
alpha push --single [/path/to/function]
```

### Promote

Will promote the given alias to the latest published version

```
# promote an entire project
alpha promote <alias_name> [/path/to/project]
```

## Contributing
This is a very early stages project. I literlly whipped it up in an afternoon.
If you'd like to contribute please fork the repo and submit a PR!
