from unittest import mock
from pathlib import Path

import pytest

import main


@mock.patch("main.requests")
def test_login_success(mock_requests):
    mock_response = mock.MagicMock()
    response_input_json = {
        "data": {
            "groups": [],
            "token": "test_token",
            "user": {
                "email": "test_user",
                "name": "test_name",
                "username": "test_username",
            },
        },
        "msg": "Successfully authenticated user and assigned a token",
        "status": "success",
        "status_code": 200,
    }
    mock_response.status_code = 200
    mock_response.json.return_value = response_input_json
    mock_requests.request.return_value = mock_response

    response = main.login("username", "password")

    assert response.status_code == 200
    assert response.json() == response_input_json


@mock.patch.object(main, "_retry_request")
def test_login_when_credentials_are_not_ok(mock_retry_request, capsys):
    mock_retry_request.side_effect = main.CouldNotAuthenticateException

    with pytest.raises(SystemExit):
        main.login("username", "password")

    captured = capsys.readouterr()

    assert (
        captured.out == "Credentials are not correct, please check the configuration.\n"
    )


@mock.patch.object(main, "_retry_request")
def test_login_cant_retry_request(mock_retry_request, capsys):
    mock_retry_request.side_effect = main.CouldNotRetryRequestException

    with pytest.raises(SystemExit):
        main.login("username", "password")

    captured = capsys.readouterr()
    assert captured.out == "Could not get response after all retries, exiting...\n"


@mock.patch("main.requests")
def test_validate_success(mock_requests, tmp_path):
    mock_response = mock.MagicMock()
    response_input_json = {
        "request_id": "1234-1234-1234-1234-1234",
        "message": "Validation request submitted.",
        "links": [
            {
                "href": "/v1/app/validate/status/1234-1234-1234-1234-1234",
                "rel": "status",
            },
            {
                "href": "/v1/app/report/1234-1234-1234-1234-1234",
                "rel": "report",
            },
        ],
    }
    mock_response.status_code = 200
    mock_response.json.return_value = response_input_json
    mock_requests.request.return_value = mock_response

    file = tmp_path / "test.spl"
    file.write_text("Mock addon")

    response = main.validate("token", file, {})

    assert response.status_code == 200
    assert response.json() == response_input_json


@mock.patch.object(main, "_retry_request")
def test_validate_invalid_token(mock_retry_request, capsys):
    mock_retry_request.side_effect = main.CouldNotAuthenticateException
    binary_file = Path("test_main.py")

    with pytest.raises(SystemExit):
        main.validate(token="token", build=binary_file, payload={})

    captured = capsys.readouterr()
    assert (
        captured.out == "Credentials are not correct, please check the configuration.\n"
    )


@mock.patch.object(main, "_retry_request")
def test_validate_count_retry(mock_retry_request, capsys):
    mock_retry_request.side_effect = main.CouldNotRetryRequestException
    binary_file = Path("test_main.py")

    with pytest.raises(SystemExit):
        main.validate(token="token", build=binary_file, payload={})

    captured = capsys.readouterr()
    assert captured.out == "Could not get response after all retries, exiting...\n"


@mock.patch("main.requests")
def test_submit_success(mock_requests):
    mock_response = mock.MagicMock()
    response_input_json = {
        "request_id": "1234-1234-1234-1234-1234",
        "links": [
            {
                "href": "/v1/app/validate/status/1234-1234-1234-1234-1234",
                "rel": "self",
            },
            {
                "href": "/v1/app/report/1234-1234-1234-1234-1234",
                "rel": "report",
            },
        ],
        "status": "SUCCESS",
        "info": {
            "error": 0,
            "failure": 0,
            "skipped": 0,
            "manual_check": 8,
            "not_applicable": 71,
            "warning": 7,
            "success": 137,
        },
    }
    mock_response.status_code = 200
    mock_response.json.return_value = response_input_json
    mock_requests.request.return_value = mock_response

    response = main.submit(token="token", request_id="1234-1234-1234")

    assert response.status_code == 200
    assert response.json() == response_input_json


@mock.patch.object(main, "_retry_request")
def test_submit_invalid_token(mock_retry_request, capsys):
    mock_retry_request.side_effect = main.CouldNotAuthenticateException

    with pytest.raises(SystemExit):
        main.submit(token="invalid_token", request_id="1234-1234")

    captured = capsys.readouterr()
    assert (
        captured.out == "Credentials are not correct, please check the configuration.\n"
    )


@mock.patch.object(main, "_retry_request")
def test_submit_cant_retry_request(mock_retry_request, capsys):
    mock_retry_request.side_effect = main.CouldNotRetryRequestException

    with pytest.raises(SystemExit):
        main.submit(token="invalid_token", request_id="1234-1234")

    captured = capsys.readouterr()
    assert captured.out == "Could not get response after all retries, exiting...\n"


@pytest.mark.parametrize(
    "included, excluded, payload",
    [
        ("a, b, c", "d, e", {"included_tags": "a, b, c", "excluded_tags": "d, e"}),
        ("", "", {}),
        ("included", "", {"included_tags": "included"}),
        ("", "excluded", {"excluded_tags": "excluded"}),
    ],
)
def test_build_payload(included, excluded, payload):
    test_payload = main.build_payload(included, excluded)
    assert test_payload == payload


@mock.patch("main.requests")
def test_download_html(mock_requests):
    mock_response = mock.MagicMock()

    sample_html = """
    <!doctype html>
    <html>
      <head>
        <title>Sample HTML</title>
      </head>
      <body>
        <p>This is sample HTML</p>
      </body>
    </html>
    """

    mock_response.text = sample_html
    mock_response.status_code = 200
    mock_requests.request.return_value = mock_response

    main.download_html_report("token", "123-123-123", {})

    with open("../../AppInspect_response.html") as test_output:
        assert test_output.read() == sample_html


def test_parse_for_errors(capsys):
    results = {"info": {"error": 1, "failure": 1}}
    with pytest.raises(SystemExit):
        main.parse_results(results)

    captured = capsys.readouterr()

    assert "Error or failures in App Inspect" in captured.out


def test_parse_for_no_errors(capsys):
    results = {"info": {"error": 0, "failure": 0}}

    main.parse_results(results)

    captured = capsys.readouterr()
    assert "{'info': {'error': 0, 'failure': 0}}\n" == captured.out


@mock.patch("main.requests")
def test_retry_request_always_400(mock_requests, capsys):
    mock_response = mock.MagicMock()
    response_input_json = {"msg": "Invalid request"}
    mock_response.json.return_value = response_input_json
    mock_response.status_code = 400
    mock_requests.request.return_value = mock_response

    with pytest.raises(main.CouldNotRetryRequestException):
        main._retry_request(
            method="GET", url="http://test", sleep=lambda _: 0.0, rand=lambda: 0.0
        )

    captured = capsys.readouterr()

    assert (
        "Sleeping 1.0 seconds before retry 1 of 2 after response status code: 400, for message: Invalid request\n"
        in captured.out
    )


@mock.patch("main.requests")
def test_retry_request_message_key_in_response(mock_requests, capsys):
    mock_response = mock.MagicMock()
    response_input_json = {"message": "message key instead of msg"}
    mock_response.json.return_value = response_input_json
    mock_response.status_code = 400
    mock_requests.request.return_value = mock_response

    with pytest.raises(main.CouldNotRetryRequestException):
        main._retry_request(
            method="GET",
            url="http://test",
            sleep=lambda _: 0.0,
            rand=lambda: 0.0,
        )

    captured = capsys.readouterr()
    assert "message key instead of msg" in captured.out


@mock.patch("main.requests")
def test_retry_request_error_401(mock_requests, capsys):
    mock_response = mock.MagicMock()
    response_input_json = {}
    mock_response.json.return_value = response_input_json
    mock_response.status_code = 401
    mock_requests.request.return_value = mock_response

    with pytest.raises(main.CouldNotAuthenticateException):
        main._retry_request(method="GET:", url="http://test")


@mock.patch("main.requests")
def test_retry_request_did_not_pass_validation(mock_requests, capsys):
    mock_response = mock.MagicMock()
    response_input_json = {"message": "message key instead of msg"}
    mock_response.json.return_value = response_input_json
    mock_response.status_code = 200
    mock_requests.request.return_value = mock_response

    with pytest.raises(main.CouldNotRetryRequestException):
        main._retry_request(
            method="GET",
            url="http://test",
            sleep=lambda _: 0.0,
            rand=lambda: 0.0,
            validation_function=lambda _: False,
        )

    captured = capsys.readouterr()

    assert "Response did not pass the validation, retrying..." in captured.out


@mock.patch("main.requests")
def test_retry_request_501_then_200(mock_request, capsys):
    mock_response_501 = mock.MagicMock()
    response_input_json_501 = {"status_code": 501, "message": "should be retried"}
    mock_response_501.json.return_value = response_input_json_501
    mock_response_501.status_code = 501

    mock_response_200 = mock.MagicMock()
    response_input_json_200 = {
        "data": {
            "groups": [],
            "token": "test_token",
            "user": {
                "email": "test_user",
                "name": "test_name",
                "username": "test_username",
            },
        },
        "msg": "Successfully authenticated user and assigned a token",
        "status": "success",
        "status_code": 200,
    }
    mock_response_200.json.return_value = response_input_json_200
    mock_response_200.status_code = 200

    mock_request.request.side_effect = [mock_response_501, mock_response_200]

    response = main._retry_request("user", "password")

    captured = capsys.readouterr()

    assert response.status_code == 200
    assert (
        "retry 1 of 2 after response status code: 501, for message: should be retried"
        in captured.out
    )


@mock.patch("main.download_html_report")
@mock.patch("main.submit")
@mock.patch("main.validate")
@mock.patch("main.login")
def test_main(mock_login, mock_validate, mock_submit, mock_download_html_report):
    # mock login
    login_mock_response = mock.MagicMock()
    response_input_json = {
        "data": {
            "groups": [],
            "token": "test_token",
            "user": {
                "email": "test_user",
                "name": "test_name",
                "username": "test_username",
            },
        },
        "msg": "Successfully authenticated user and assigned a token",
        "status": "success",
        "status_code": 200,
    }
    login_mock_response.status_code = 200
    login_mock_response.json.return_value = response_input_json
    mock_login.return_value = login_mock_response

    # mock validate
    validate_mock_response = mock.MagicMock()
    response_input_json = {
        "request_id": "1234-1234-1234-1234-1234",
        "message": "Validation request submitted.",
        "links": [
            {
                "href": "/v1/app/validate/status/1234-1234-1234-1234-1234",
                "rel": "status",
            },
            {
                "href": "/v1/app/report/1234-1234-1234-1234-1234",
                "rel": "report",
            },
        ],
    }
    validate_mock_response.status_code = 200
    validate_mock_response.json.return_value = response_input_json
    mock_validate.return_value = validate_mock_response

    # mock submit
    submit_mock_response = mock.MagicMock()
    response_input_json = {
        "request_id": "1234-1234-1234-1234-1234",
        "links": [
            {
                "href": "/v1/app/validate/status/1234-1234-1234-1234-1234",
                "rel": "self",
            },
            {
                "href": "/v1/app/report/1234-1234-1234-1234-1234",
                "rel": "report",
            },
        ],
        "status": "SUCCESS",
        "info": {
            "error": 0,
            "failure": 0,
            "skipped": 0,
            "manual_check": 8,
            "not_applicable": 71,
            "warning": 7,
            "success": 137,
        },
    }
    submit_mock_response.status_code = 200
    submit_mock_response.json.return_value = response_input_json
    mock_submit.return_value = submit_mock_response

    # mock download
    download_mock_response = mock.MagicMock()
    sample_html = """
        <!doctype html>
        <html>
          <head>
            <title>Sample HTML</title>
          </head>
          <body>
            <p>This is sample HTML</p>
          </body>
        </html>
    """
    download_mock_response.text = sample_html
    download_mock_response.status_code = 200
    mock_download_html_report.request.return_value = download_mock_response

    main.main(["user", "pass", "build", "i_tag", "e_tag"])


@mock.patch("main.validate")
@mock.patch("main.login")
def test_main_invalid_token(mock_login, mock_validate):
    # mock login
    login_mock_response = mock.MagicMock()
    response_input_json = {
        "data": {
            "groups": [],
            "token": "test_token",
            "user": {
                "email": "test_user",
                "name": "test_name",
                "username": "test_username",
            },
        },
        "msg": "Successfully authenticated user and assigned a token",
        "status": "success",
        "status_code": 200,
    }
    login_mock_response.status_code = 200
    login_mock_response.json.return_value = response_input_json
    mock_login.return_value = login_mock_response

    # mock validate throwing out 401
    mock_validate.side_effect = main.CouldNotAuthenticateException

    with pytest.raises(main.CouldNotAuthenticateException):
        main.main(["user", "pass", "build", "i_tag", "e_tag"])


@mock.patch("main.login")
def test_main_api_down_cant_retry_request(mock_login):
    mock_login.side_effect = main.CouldNotRetryRequestException

    with pytest.raises(main.CouldNotRetryRequestException):
        main.main(["user", "pass", "build", "i_tag", "e_tag"])