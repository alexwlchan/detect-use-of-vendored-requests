#!/usr/bin/env python3
"""
This script tries to find Lambda functions in your AWS account that use
the now-deprecated ``from botocore.vendored import requests``.

It flags Lambdas that might need attention, but it's not foolproof.  If you
absolutely depend on the uptime of your Lambdas, you might want to do
additional checks.
"""

import os
import shutil
import tempfile
from urllib.request import urlretrieve

import boto3


def get_all_functions(lambda_client):
    """
    Generates every Lambda function in an AWS account.
    """
    paginator = lambda_client.get_paginator("list_functions")

    for page in paginator.paginate():
        yield from page["Functions"]


def get_lambda_source_code(lambda_client, function_name):
    """
    Downloads all the source code for a Lambda function to a temporary
    directory, and returns the path to the temp dir.
    """
    resp = lambda_client.get_function(FunctionName=function_name)

    # In the description of a Lambda function, the .Code.Location field
    # contains a presigned URL that we can use to download the deployment
    # package, aka the code running this Lambda.
    filename, headers = urlretrieve(resp["Code"]["Location"])

    # I think all Lambda deployment packages are zip archives, but let's
    # double check to be sure.
    if headers.get("Content-Type") == "application/zip":
        archive_format = "zip"
    else:
        raise RuntimeError(
            "Unrecognised Content-Type in deployment package for %s: %s"
            % (function_name, headers.get("Content-Type"))
        )

    # Now unpack the source code into a temporary directory
    working_dir = tempfile.mkdtemp()
    shutil.unpack_archive(
        filename=filename, extract_dir=working_dir, format=archive_format
    )

    return working_dir


def find_python_paths(root):
    """
    Generates every path to a Python file under a given root directory.
    """
    for dirpath, _, filenames in os.walk(root):
        for f in filenames:
            if f.endswith(".py"):
                yield os.path.join(dirpath, f)


def contains_vendored_imports(python_path):
    """
    Returns True if ``python_path`` seems to contain vendored imports from botocore.
    """
    # We're using a very rough heuristic here: if the source code contains
    # strings that look like a vendored import, we'll flag.
    #
    # Because Python is dynamic, there are lots of ways you could be
    # importing the vendored modules that wouldn't be caught this way, but:
    #
    #   1.  Doing it in a complete foolproof way is incredibly complicated, and
    #       I don't care that much.
    #   2.  If you're writing your Lambda code in a deliberately obfuscated way,
    #       you have bigger problems than vendor deprecations.
    #
    # In practice, Python imports are usually near the top of the file, so we
    # read it line-by-line.  This means if we find an import, we can skip
    # reading the rest of the file.
    #
    with open(python_path, "rb") as python_src:
        for line in python_src:
            if (
                b"import botocore.vendored" in line
                or b"from botocore.vendored import " in line
            ):
                return True

    return False


class bcolors:
    # https://stackoverflow.com/a/287944/1558022
    OKGREEN = "\033[92m"
    FAIL = "\033[91m"
    ENDC = "\033[0m"
    UNDERLINE = "\033[4m"


def pretty_function_name(function_name):
    return bcolors.UNDERLINE + function_name + bcolors.ENDC


if __name__ == "__main__":
    lambda_client = boto3.client("lambda")

    for lambda_function in get_all_functions(lambda_client):

        # The botocore deprecation only affects Python Lambdas, so we can
        # skip Lambdas that use a different runtime.
        if "python" not in lambda_function["Runtime"]:
            continue

        function_name = lambda_function["FunctionName"]

        source_code_dir = get_lambda_source_code(
            lambda_client, function_name=function_name
        )

        paths_with_vendored_imports = []

        for python_path in find_python_paths(source_code_dir):
            # The botocore/boto3 libraries themselves will import from botocore,
            # but this is fine and not a cause for concern (probably).
            if os.path.relpath(python_path, source_code_dir).startswith(
                ("boto3/", "botocore/")
            ):
                continue

            if contains_vendored_imports(python_path):
                paths_with_vendored_imports.append(
                    os.path.relpath(python_path, source_code_dir)
                )

        if paths_with_vendored_imports:
            print(
                "[%sFAIL%s] Vendored imports detected in %s:"
                % (bcolors.FAIL, bcolors.ENDC, pretty_function_name(function_name))
            )
            for path in sorted(paths_with_vendored_imports):
                print("       - %s" % path)
        else:
            # Prints "OK" in green.  See https://stackoverflow.com/a/287944/1558022
            print(
                "[ %sOK%s ] No vendored imports in %s"
                % (bcolors.OKGREEN, bcolors.ENDC, pretty_function_name(function_name))
            )
