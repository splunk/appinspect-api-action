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
APPINSPECT_EXPECT_FILENAME = ".appinspect_api.expect.yaml"


class CouldNotAuthenticateException(Exception):
    pass


class CouldNotRetryRequestException(Exception):
    pass


logger = logging.getLogger("splunk_appinspect_api")
logger.setLevel(logging.INFO)
formatter = logging.Formatter("%(levelname)s: %(message)s")
stream_handler = logging.StreamHandler()
stream_handler.setLevel(logging.INFO)
stream_handler.setFormatter(formatter)
logger.addHandler(stream_handler)


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
) -> requests.Response:
    reason = ""
    for retry_num in range(num_retries):
        if retry_num > 0:
            sleep_time = rand() + retry_num
            logger.info(
                f"Sleeping {sleep_time} seconds before retry "
                f"{retry_num} of {num_retries - 1}"
            )
            if reason:
                logger.info(reason)
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
    logger.debug("Sending request to retrieve login token")
    try:
        return _retry_request(
            "GET",
            "https://api.splunk.com/2.0/rest/login/splunk",
            auth=(username, password),
        )
    except CouldNotAuthenticateException:
        logger.error("Credentials are not correct, please check the configuration.")
        sys.exit(1)
    except CouldNotRetryRequestException:
        logger.error("Could not get response after all retries, exiting...")
        sys.exit(1)


def validate(token: str, build: Path, payload: Dict[str, str]) -> requests.Response:
    files = [
        (
            "app_package",
            (build.name, open(build.as_posix(), "rb"), "application/octet-stream"),
        )
    ]
    logger.debug(f"Sending package `{build.name}` for validation")
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
        logger.error("Credentials are not correct, please check the configuration.")
        sys.exit(1)
    except CouldNotRetryRequestException:
        logger.error("Could not get response after all retries, exiting...")
        sys.exit(1)


def submit(
    token: str, request_id: str, seconds_to_wait: float = 60.0
) -> requests.Response:
    def _validate_validation_status(response: requests.Response) -> bool:
        status = response.json()["status"]
        is_successful = status == "SUCCESS"
        if not is_successful:
            logger.info(f'Response status is `{status}`, "SUCCESS" expected.')
        return is_successful

    # Splunk AppInspect API needs some time to process the request.
    # If the response status will be "PROCESSING" wait 60s and make another call.

    # There is a problem with pytest-cov marking this line as not covered - excluded from coverage.
    try:
        logger.debug("Submitting package")
        return _retry_request(  # pragma: no cover
            "GET",
            f"https://appinspect.splunk.com/v1/app/validate/status/{request_id}",
            headers={
                "Authorization": f"bearer {token}",
            },
            rand=lambda: seconds_to_wait,
            num_retries=40,
            validation_function=_validate_validation_status,
        )
    except CouldNotAuthenticateException:
        logger.error("Credentials are not correct, please check the configuration.")
        sys.exit(1)
    except CouldNotRetryRequestException:
        logger.error("Could not get response after all retries, exiting...")
        sys.exit(1)


def download_json_report(
    token: str, request_id: str, payload: Dict[str, Any]
) -> requests.Response:
    logger.info("Downloading response in JSON format")
    return _download_report(
        token=token, request_id=request_id, payload=payload, response_type="json"
    )


def download_and_save_html_report(token: str, request_id: str, payload: Dict[str, Any]):
    logger.info("Downloading report in HTML format")
    response = _download_report(
        token=token, request_id=request_id, payload=payload, response_type="html"
    )

    with open("AppInspect_response.html", "w") as f:
        f.write(response.text)


def get_appinspect_failures_list(response_dict: Dict[str, Any]) -> List[str]:
    logger.debug("Parsing JSON response to find failed checks")
    reports = response_dict["reports"]
    groups = reports[0]["groups"]
    failed_tests_list = []
    for group in groups:
        for check in group["checks"]:
            if check["result"] == "failure":
                failed_tests_list.append(check["name"])
                logger.info(f"Failed AppInspect check for name: {check['name']}")
                check_messages = check["messages"]
                for check_message in check_messages:
                    logger.info(f"\t* {check_message['message']}")
    return failed_tests_list


def read_yaml_as_dict(filename_path: Path) -> Dict[str, str]:
    with open(filename_path) as file:
        try:
            out_dict = yaml.safe_load(file)
        except yaml.YAMLError as e:
            logger.error(f"Can not read YAML file named {filename_path}")
            raise e
    return out_dict if out_dict else {}


def build_payload(included_tags: str, excluded_tags: str) -> Dict[str, str]:
    payload = {}
    if included_tags != "":
        payload["included_tags"] = included_tags
    if excluded_tags != "":
        payload["excluded_tags"] = excluded_tags
    return payload


def compare_against_known_failures(
    response_json: Dict[str, Any], exceptions_file_path: Path
) -> None:
    logger.info(
        f"Comparing AppInspect failures with `{exceptions_file_path.name}` file"
    )
    failures = get_appinspect_failures_list(response_json)

    if exceptions_file_path.exists():
        expected_failures = list(read_yaml_as_dict(exceptions_file_path).keys())
        if sorted(failures) != sorted(expected_failures):
            logger.info(f"AppInspect failures: {failures}")
            logger.info(f"Expected failures: {expected_failures}")
            logger.error(
                "AppInspect failures don't match appinspect.expect file, check for exceptions file"
            )
            sys.exit(1)
    else:
        logger.error(
            f"File `{exceptions_file_path.name}` not found, "
            f"please create `{exceptions_file_path.name}` file with exceptions"
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
    parser.add_argument("log_level")

    args = parser.parse_args(argv)

    logger.setLevel(args.log_level)

    logger.info(
        f"Running Splunk AppInspect API for app_path={args.app_path}, "
        f"included_tags={args.included_tags}, excluded_tags={args.excluded_tags}"
    )
    build = Path(args.app_path)

    login_response = login(args.username, args.password)
    token = login_response.json()["data"]["token"]
    logger.info("Successfully received token after login")

    payload = build_payload(args.included_tags, args.excluded_tags)
    logger.info(f"Validation payload {payload}")

    validate_response = validate(token, build, payload)
    logger.info(f"Successfully sent package for validation using {payload}")
    request_id = validate_response.json()["request_id"]

    submit_response = submit(token, request_id)
    logger.info("Successfully submitted and validated package")
    submit_response_info = submit_response.json()["info"]
    logger.info(f"Report info {submit_response_info}")
    download_and_save_html_report(token, request_id, payload)

    issues_in_response = False
    if submit_response_info["error"] > 0 or submit_response_info["failure"] > 0:
        issues_in_response = True

    if issues_in_response:
        logger.info("Detected errors / failures in response")
        response_in_json = download_json_report(token, request_id, payload)
        response_json = json.loads(response_in_json.content.decode("utf-8"))
        yaml_file_path = Path(APPINSPECT_EXPECT_FILENAME).absolute()
        compare_against_known_failures(response_json, yaml_file_path)


if __name__ == "__main__":
    main()
