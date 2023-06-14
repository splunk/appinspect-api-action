import sys
import requests
import argparse
import time
import random

from pathlib import Path
from typing import Dict, Any, Tuple, Callable, Sequence, Optional

NUM_RETRIES = 3


class CouldNotAuthenticateException(Exception):
    pass


class CouldNotRetryRequestException(Exception):
    pass


def _retry_request(
    method: str,
    url: str,
    data: Optional[Dict[str, Any]] = None,
    headers: Optional[Dict[str, Any]] = None,
    params: Optional[Dict[str, Any]] = None,
    auth: Optional[Tuple[str, str]] = None,
    files: Optional[Sequence[Tuple[str, Any]]] = None,
    timeout: int = 60,
    num_retries: int = NUM_RETRIES,
    sleep: Callable[[float], Any] = time.sleep,
    rand: Callable[[], float] = random.random,
    validation_function: Callable[[requests.Response], bool] = lambda _: True,
):
    reason = ""
    for retry_num in range(num_retries):
        if retry_num > 0:
            sleep_time = rand() + retry_num
            print(
                f"Sleeping {sleep_time} seconds before retry "
                f"{retry_num} of {num_retries - 1} after {reason}"
            )
            sleep(sleep_time)
        response = requests.request(
            method,
            url,
            data=data,
            headers=headers,
            params=params,
            files=files,
            auth=auth,
            timeout=timeout,
        )
        # TODO:
        # Check if appinspect api gives 401 on
        # I think it gives 400 and error message
        if response.status_code == 401:
            raise CouldNotAuthenticateException()
        if 400 <= response.status_code < 600:
            error_message = response.json().get("msg", None)
            if not error_message:
                error_message = response.json().get("message", "unknown error message")
            reason = f"response status code: {response.status_code}, for message: {error_message}"
            continue
        if not validation_function(response):
            print("Response did not pass the validation, retrying...")
            continue
        return response
    raise CouldNotRetryRequestException()


def login(username: str, password: str) -> requests.Response:
    try:
        return _retry_request(
            "GET",
            "https://api.splunk.com/2.0/rest/login/splunk",
            auth=(username, password),
        )
    except CouldNotAuthenticateException:
        print("Credentials are not correct, please check the configuration.")
        sys.exit(1)
    except CouldNotRetryRequestException:
        print("Could not get response after all retries, exiting...")
        sys.exit(1)


def validate(token: str, build, payload):
    files = [
        (
            "app_package",
            (build.name, open(build.as_posix(), "rb"), "application/octet-stream"),
        )
    ]
    try:
        response = _retry_request(
            "POST",
            "https://appinspect.splunk.com/v1/app/validate",
            headers={
                "Authorization": f"bearer {token}",
            },
            data=payload,
            files=files,
        )
        return response
    except CouldNotAuthenticateException:
        print("Credentials are not correct, please check the configuration.")
        sys.exit(1)
    except CouldNotRetryRequestException:
        print("Could not get response after all retries, exiting...")
        sys.exit(1)


def submit(token: str, request_id: str) -> requests.Response:
    def _validate_validation_status(response: requests.Response) -> bool:
        return response.json()["status"] == "SUCCESS"

    # appinspect api needs some time to process the request
    # if the response status will be "PROCESSING" wait 60s and make another call

    # there is a problem with pycov marking this line as not covered - excluded from coverage
    try:
        return _retry_request(  # pragma: no cover
            "GET",
            f"https://appinspect.splunk.com/v1/app/validate/status/{request_id}",
            headers={
                "Authorization": f"bearer {token}",
            },
            rand=lambda: 60.0,
            num_retries=10,
            validation_function=_validate_validation_status,
        )
    except CouldNotAuthenticateException:
        print("Credentials are not correct, please check the configuration.")
        sys.exit(1)
    except CouldNotRetryRequestException:
        print("Could not get response after all retries, exiting...")
        sys.exit(1)


def download_html_report(token: str, request_id: str, payload: Dict[str, Any]):
    response = _retry_request(
        "GET",
        f"https://appinspect.splunk.com/v1/app/report/{request_id}",
        headers={"Authorization": f"bearer {token}", "Content-Type": "text/html"},
        data=payload,
    )

    with open("AppInspect_response.html", "w") as f:
        f.write(response.text)


def parse_results(results):
    print(results)
    print(f"\n======== AppInspect Api Results ========")
    for metric, count  in results["info"].items():
        print("{0:>15}    :    {1: <4}".format(metric, count))
    if results["info"]["error"] > 0 or results["info"]["failure"] > 0:
        print("Error or failures in App Inspect")
        sys.exit(1)


def build_payload(included_tags: str, excluded_tags: str):
    payload = {}
    if included_tags != "":
        payload["included_tags"] = included_tags
    if excluded_tags != "":
        payload["excluded_tags"] = excluded_tags

    return payload


def main(argv: Optional[Sequence[str]] = None):
    argv = argv if argv is not None else sys.argv[1:]

    parser = argparse.ArgumentParser()
    parser.add_argument("username")
    parser.add_argument("password")
    parser.add_argument("app_path")
    parser.add_argument("included_tags")
    parser.add_argument("excluded_tags")

    args = parser.parse_args(argv)

    print(
        f"app_path={args.app_path}, included_tags={args.included_tags}, excluded_tags={args.excluded_tags}"
    )
    build = Path(args.app_path)

    login_response = login(args.username, args.password)
    token = login_response.json()["data"]["token"]
    print("Successfully received token")

    payload = build_payload(args.included_tags, args.excluded_tags)

    validate_response = validate(token, build, payload)
    print(f"Successfully sent package for validation using {payload}")
    request_id = validate_response.json()["request_id"]

    submit_response = submit(token, request_id)
    download_html_report(token, request_id, payload)
    parse_results(submit_response.json())


if __name__ == "__main__":
    main()
