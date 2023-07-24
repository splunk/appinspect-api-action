import sys
import requests
import argparse
import time
import random
import json
import yaml
import logging

from pathlib import Path
from typing import Dict, Any, Tuple, Callable, Sequence, Optional, List

NUM_RETRIES = 3

logging.basicConfig(level=logging.INFO)


class CouldNotAuthenticateException(Exception):
    pass


class CouldNotRetryRequestException(Exception):
    pass


class AppinspectChecksFailuresException(Exception):
    pass


class AppinspectFailures(Exception):
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
            logging.info(
                f"Sleeping {sleep_time} seconds before retry "
                f"{retry_num} of {num_retries - 1}"
            )
            if reason:
                logging.info(reason)
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
        if response.status_code == 401:
            raise CouldNotAuthenticateException()
        if 400 <= response.status_code < 600:
            error_message = response.json().get("msg", None)
            if not error_message:
                error_message = response.json().get("message", "unknown error message")
            reason = f"response status code: {response.status_code}, for message: {error_message}"
            continue
        if not validation_function(response):
            logging.info("Response did not pass the validation, retrying...")
            continue
        return response
    raise CouldNotRetryRequestException()


def _download_report(
    token: str, request_id: str, payload: Dict[str, Any], response_type: str
) -> requests.Response:
    response_types = {"html": "text/html", "json": "application/json"}

    return _retry_request(
        "GET",
        f"https://appinspect.splunk.com/v1/app/report/{request_id}",
        headers={
            "Authorization": f"bearer {token}",
            "Content-Type": response_types[response_type],
        },
        data=payload,
    )


def login(username: str, password: str) -> requests.Response:
    logging.debug("Sending request to retrieve login token")
    try:
        return _retry_request(
            "GET",
            "https://api.splunk.com/2.0/rest/login/splunk",
            auth=(username, password),
        )
    except CouldNotAuthenticateException:
        logging.error("Credentials are not correct, please check the configuration.")
        sys.exit(1)
    except CouldNotRetryRequestException:
        logging.error("Could not get response after all retries, exiting...")
        sys.exit(1)


def validate(token: str, build: Path, payload: Dict[str, str]) -> requests.Response:
    files = [
        (
            "app_package",
            (build.name, open(build.as_posix(), "rb"), "application/octet-stream"),
        )
    ]
    logging.debug(f"Sending package {build.name} for validation")
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
        logging.error("Credentials are not correct, please check the configuration.")
        sys.exit(1)
    except CouldNotRetryRequestException:
        logging.error("Could not get response after all retries, exiting...")
        sys.exit(1)


def submit(token: str, request_id: str) -> requests.Response:
    def _validate_validation_status(response: requests.Response) -> bool:
        is_successful = response.json()["status"] == "SUCCESS"
        if is_successful:
            logging.info('Response status is not "SUCCESS"')
        return is_successful

    # appinspect api needs some time to process the request
    # if the response status will be "PROCESSING" wait 60s and make another call

    # there is a problem with pycov marking this line as not covered - excluded from coverage
    try:
        logging.debug("Submitting package")
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
        logging.error("Credentials are not correct, please check the configuration.")
        sys.exit(1)
    except CouldNotRetryRequestException:
        logging.error("Could not get response after all retries, exiting...")
        sys.exit(1)


def download_json_report(
    token: str, request_id: str, payload: Dict[str, Any]
) -> requests.Response:
    logging.debug("Downloading response in json format")
    return _download_report(
        token=token, request_id=request_id, payload=payload, response_type="json"
    )


def download_and_save_html_report(token: str, request_id: str, payload: Dict[str, Any]):
    logging.debug("Downloading report in html format")
    response = _download_report(
        token=token, request_id=request_id, payload=payload, response_type="html"
    )

    with open("AppInspect_response.html", "w") as f:
        f.write(response.text)


def get_appinspect_failures_list(response_dict: Dict[str, Any]) -> List[str]:
    logging.debug(
        f"Parsing json respnose to find failed checks\n response: {response_dict}"
    )
    reports = response_dict["reports"]
    groups = reports[0]["groups"]

    failed_tests_list = []

    for group in groups:
        for check in group["checks"]:
            if check["result"] == "failure":
                failed_tests_list.append(check["name"])
                logging.debug(f"Failed appinspect check for name: {check['name']}\n")
    return failed_tests_list


def read_yaml_as_dict(filename_path: Path) -> Dict[str, str]:
    with open(filename_path) as file:
        try:
            out_dict = yaml.safe_load(file)
        except yaml.YAMLError as e:
            logging.error(f"Can not read yaml file named {filename_path}")
            raise e
    return out_dict if out_dict else {}


def compare_failures(failures: List[str], expected: List[str]):
    if sorted(failures) != sorted(expected):
        logging.error(
            "Appinspect failures doesn't match appinspect.expect file, check for exceptions file"
        )
        raise AppinspectFailures


def parse_results(results: Dict[str, Any]):
    print("\n======== AppInspect Api Results ========")
    for metric, count in results["info"].items():
        print(f"{metric:>15}    :    {count: <4}")
    if results["info"]["error"] > 0 or results["info"]["failure"] > 0:
        logging.error("\nError or failures found in App Inspect\n")
        raise AppinspectChecksFailuresException


def build_payload(included_tags: str, excluded_tags: str) -> Dict[str, str]:
    payload = {}
    if included_tags != "":
        payload["included_tags"] = included_tags
    if excluded_tags != "":
        payload["excluded_tags"] = excluded_tags

    return payload


def compare_against_known_failures(response_json: Dict[str, Any], exceptions_file_path):
    failures = get_appinspect_failures_list(response_json)

    if exceptions_file_path.exists():
        expected_failures = list(read_yaml_as_dict(exceptions_file_path).keys())
        compare_failures(failures, expected_failures)
    else:
        logging.error(
            f"File `{exceptions_file_path.name}` not found, please create `{exceptions_file_path.name}` file with exceptions\n"  # noqa: E501
        )
        sys.exit(1)


def main(argv: Optional[Sequence[str]] = None):
    argv = argv if argv is not None else sys.argv[1:]

    parser = argparse.ArgumentParser()
    parser.add_argument("username")
    parser.add_argument("password")
    parser.add_argument("app_path")
    parser.add_argument("included_tags")
    parser.add_argument("excluded_tags")

    appinspect_expect_filename = ".appinspect_api.expect.yaml"

    args = parser.parse_args(argv)

    print(
        f"app_path={args.app_path}, included_tags={args.included_tags}, excluded_tags={args.excluded_tags}"
    )
    build = Path(args.app_path)

    login_response = login(args.username, args.password)
    token = login_response.json()["data"]["token"]
    logging.info("Successfully received token")

    payload = build_payload(args.included_tags, args.excluded_tags)

    validate_response = validate(token, build, payload)
    logging.info(f"Successfully sent package for validation using {payload}")
    request_id = validate_response.json()["request_id"]

    submit_response = submit(token, request_id)
    download_and_save_html_report(token, request_id, payload)

    # if this is true it compares the exceptions and results
    try:
        parse_results(submit_response.json())
    except AppinspectChecksFailuresException:
        response_in_json = download_json_report(token, request_id, payload)
        response_json = json.loads(response_in_json.content.decode("utf-8"))
        yaml_file_path = Path(appinspect_expect_filename).absolute()

        compare_against_known_failures(response_json, yaml_file_path)


if __name__ == "__main__":
    main()
