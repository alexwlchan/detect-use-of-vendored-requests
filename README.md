# detect-use-of-vendored-requests

**This script tries to find Lambda functions in your AWS account that use the now-deprecated `from botocore.vendored import requests`.**

It flags Lambdas that might need attention, but it's not foolproof.
If you absolutely depend on the uptime of your Lambdas, you might want to do additional checks.



## Motivation

For a long time, you've been able to access the Python requests library from inside an AWS Lambda by importing the version that was vendored with botocore:

```python
from botocore.vendored import requests
```

At the beginning of this year, AWS announced [that this was deprecated](https://aws.amazon.com/blogs/compute/upcoming-changes-to-the-python-sdk-in-aws-lambda/).
You need to install `requests` as part of your Lambda's deployment package, or it will stop working at some date in the future (currently March 2021).

This news ahd completely passed me by until I saw a tweet from [Eric Hammond](https://twitter.com/esh/status/1237436147409666048):

> \#awswishlist (that any one of us can develop)
>
> aws-cli script that iterates through all python AWS Lambda functions in an account, downloads the source, and determines which import requests from botocore vendored.
>
> Or we can be surprised in a year. <https://twitter.com/jbesw/status/1237382195532238848>

This script is an attempt to plug that gap.



## Usage

Download the Python script in the root of this repo.
It needs Python 3 and the boto3 SDK installed locally (`pip3 install --user boto3`).

Get [some credentials](https://boto3.amazonaws.com/v1/documentation/api/latest/guide/configuration.html?highlight=credentials) for the AWS account you want to check, then run the script:

```console
$ python3 detect_use_of_vendored_requests.py
```

It will go through all the Python Lambda functions in your account, and for each function run some simple heuristics to see if there are deprecated imports you need to fix.

Here's an example of the output:

```console
$ python3 detect_use_of_vendored_requests.py
[ OK ] No vendored imports in good_lambda_1
[ OK ] No vendored imports in good_lambda_2
[FAIL] Vendored imports detected in bad_lambda_1:
       - use_vendored_requests_file_1.py
       - module/use_vendored_requests_file_2.py
```

You should investigate any Lambdas that it flags, and update them to install requests directly before the cutoff point.



## Limitations

The script uses a very rough heuristic to detect vendored imports: it looks for strings in the source code that look like a vendored import.

Because Python is dynamic, there are lots of ways you could be importing the vendored modules that wouldn't be caught this way, but:

1. Detect imports in a completely foolproof way is incredibly complicated, and I don't care that much.
2. If you're writing your Lambda code in a deliberately obfuscated way, you have bigger problems than vendor deprecations.



## License

CC0.
