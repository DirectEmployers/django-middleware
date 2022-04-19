"""
This file contains boilerplate code for accessing the user-management pod
"""
import requests


def get_session_company_id(incoming_request) -> int:
    """
    gets returns company_id of the company for current django session.
    :param incoming_request: django HTTPRequest object
    :return: id for seo.models.Company
    """
    return get_session_company(incoming_request)["company"]["id"]


def get_session_company(incoming_request) -> dict:
    """
    This function sends a request to user-management to get the company-info for the
    current django session id.
    :param incoming_request: django HTTPrequest object
    :return: dictionary containing the json response from the user-management pod
    """
    url = "http://user-management:8000/api/session_company/"
    response = requests.get(url, cookies=incoming_request.COOKIES)
    response.raise_for_status()
    if response.headers["Content-Type"] != "application/json":
        raise requests.HTTPError(
            "Invalid content-type '%s' returned" % response.headers["Content-Type"]
        )
    return response.json()
