import base64
import json
import os
import requests
import urllib.parse
from datetime import datetime

from cremalink.resources.api_config import load_api_config
from cremalink.resources.lang import load_lang_config

class CloudToken:
    """
    Responsible for handling authentication with the Ayla IoT cloud platform.
    This module implements the multi-step authentication flow required to obtain a refresh token, which can be used for API interactions.
    """
    def __init__(self, refresh_token: str):
        self.refresh_token = refresh_token

    """
    Saves the refresh token to a JSON file at the specified path. The file will contain a single key "refresh_token" with the token value. If the file already exists, it will be overwritten.
    
    Args:
        path (str): The file path where the token should be saved. Defaults to "token.json".
    
    Returns:
        str: The absolute path to the saved token file.
    """
    def save(self, path: str = "token.json") -> str:
        abs_path = os.path.abspath(path)
        with open(abs_path, "w", encoding="utf-8") as f:
            json.dump({"refresh_token": self.refresh_token}, f, indent=2)
        return abs_path

    """
    Returns a string representation of the CloudToken instance, which is the refresh token itself. This allows for easy printing or logging of the token value when the instance is converted to a string.
    
    Returns:
        str: The refresh token contained in the CloudToken instance.
    """
    def __str__(self):
        return self.refresh_token


def _get_query_param(url: str, param: str):
    query = urllib.parse.urlparse(url).query
    params = urllib.parse.parse_qs(query)
    return params.get(param, [None])[0]


def authenticate_cloud(email: str, password: str, language: str = "en") -> CloudToken:
    """
    Performs the multi-step authentication flow to obtain a refresh token for the Ayla IoT cloud platform.

    This function executes the following steps:
    1. Authorize: Initiates the authorization process to obtain a context parameter.
    2. Get IDs: Retrieves necessary IDs (ucid, gmid, gmid_ticket) for the login process.
    3. Login: Authenticates the user with their email and password, along with risk context information, to obtain a login token.
    4. Get User Info: Fetches user information using the login token to obtain UID, UIDSignature, and signatureTimestamp.
    5. Consent: Simulates the user consent process to obtain a signature for the authorization continue step.
    6. Authorization Continue: Continues the authorization process using the context, login token, and consent signature to obtain an authorization code.
    7. IDP Token: Exchanges the authorization code for an IDP token.
    8. Exchange for Ayla: Uses the IDP token to sign in to the Ayla cloud and obtain a refresh token.

    Args:
        email (str): The user's email address for authentication.
        password (str): The user's password for authentication.
        language (str): The preferred language for the authentication process (default is "en").

    Returns:
        CloudToken: An instance of CloudToken containing the obtained refresh token.
    """

    api_conf = load_api_config()
    gigya_key = api_conf["GIGYA"]["API_KEY"]
    client_id = api_conf["GIGYA"]["CLIENT_ID"]
    client_secret = api_conf["GIGYA"]["CLIENT_SECRET"]
    sdk_build = api_conf["GIGYA"]["SDK_BUILD"]
    app_id = api_conf["AYLA"]["APP_ID"]
    app_secret = api_conf["AYLA"]["APP_SECRET"]

    browser_agent = api_conf["USER_AGENT"]["BROWSER"]
    token_agent = api_conf["USER_AGENT"]["TOKEN"]

    auth_header = "Basic " + base64.b64encode(f"{client_id}:{client_secret}".encode()).decode()

    lang_conf = load_lang_config()
    supported_langs = lang_conf.get("languages", {})
    if language not in supported_langs:
        language = "en"

    # Step 1: Authorize
    res = requests.get(
        f"https://fidm.eu1.gigya.com/oidc/op/v1.0/{gigya_key}/authorize",
        headers={"User-Agent": browser_agent},
        params={
            "client_id": client_id,
            "response_type": "code",
            "redirect_uri": "https://google.it",
            "scope": "openid email profile UID comfort en alexa",
            "nonce": str(int(datetime.now().timestamp())),
        },
        allow_redirects=False,
    )
    context = _get_query_param(res.headers.get("Location", ""), "context")

    # Step 2: Get IDs
    res = requests.get(
        "https://socialize.eu1.gigya.com/socialize.getIDs",
        headers={"User-Agent": browser_agent},
        params={
            "APIKey": gigya_key,
            "includeTicket": True,
            "pageURL": "https://aylaopenid.delonghigroup.com/",
            "sdk": "js_latest",
            "sdkBuild": sdk_build,
            "format": "json",
        },
    ).json()
    ucid = res.get("ucid")
    gmid = res.get("gmid")
    gmid_ticket = res.get("gmidTicket")

    # Step 3: Login
    risk_context_json = json.dumps({
        "b0": 4494, "b1": [0, 2, 2, 0], "b2": 2, "b3": [], "b4": 2, "b5": 1,
        "b6": browser_agent,
        "b7": [{"name": "PDF Viewer", "filename": "internal-pdf-viewer", "length": 2}],
        "b8": datetime.now().strftime("%H:%M:%S"),
        "b9": 0, "b10": {"state": "denied"}, "b11": False,
        "b13": [5, "440|956|24", False, True],
    })

    res = requests.post(
        "https://accounts.eu1.gigya.com/accounts.login",
        headers={"User-Agent": browser_agent},
        data={
            "loginID": email,
            "password": password,
            "sessionExpiration": 7884009,
            "targetEnv": "jssdk",
            "include": "profile,data,emails,subscriptions,preferences",
            "includeUserInfo": True,
            "loginMode": "standard",
            "lang": language,
            "riskContext": urllib.parse.quote(risk_context_json),
            "APIKey": gigya_key,
            "source": "showScreenSet",
            "sdk": "js_latest",
            "authMode": "cookie",
            "pageURL": "https://aylaopenid.delonghigroup.com/",
            "gmid": gmid,
            "ucid": ucid,
            "sdkBuild": sdk_build,
            "format": "json",
        },
    ).json()

    if "sessionInfo" not in res:
        raise ValueError(f"Gigya Login failed: {res}")

    login_token = res["sessionInfo"]["login_token"]

    # Step 4: Get User Info
    res = requests.post(
        "https://socialize.eu1.gigya.com/socialize.getUserInfo",
        headers={"User-Agent": browser_agent},
        data={
            "enabledProviders": "*",
            "APIKey": gigya_key,
            "sdk": "js_latest",
            "login_token": login_token,
            "authMode": "cookie",
            "pageURL": "https://aylaopenid.delonghigroup.com/",
            "gmid": gmid,
            "ucid": ucid,
            "sdkBuild": sdk_build,
            "format": "json",
        },
    ).json()
    user_uid = res["UID"]
    user_uid_sig = res["UIDSignature"]
    user_sig_ts = res["signatureTimestamp"]

    # Step 5: Consent
    res = requests.get(
        "https://aylaopenid.delonghigroup.com/OIDCConsentPage.php",
        headers={"User-Agent": browser_agent},
        params={
            "lang": language,
            "context": context,
            "clientID": client_id,
            "scope": "openid+email+profile+UID+comfort+en+alexa",
            "UID": user_uid,
            "UIDSignature": user_uid_sig,
            "signatureTimestamp": user_sig_ts,
        },
    ).text
    signature = res.split("const consentObj2Sig = '")[1].split("';")[0]

    # Step 6: Authorization Continue
    res = requests.get(
        f"https://fidm.eu1.gigya.com/oidc/op/v1.0/{gigya_key}/authorize/continue",
        headers={"User-Agent": browser_agent},
        params={
            "context": context,
            "login_token": login_token,
            "consent": json.dumps(
                {"scope": "openid email profile UID comfort en alexa", "clientID": client_id, "context": context,
                 "UID": user_uid, "consent": True},
                separators=(",", ":")
            ),
            "sig": signature,
            "gmidTicket": gmid_ticket,
        },
        allow_redirects=False,
    )
    code = _get_query_param(res.headers.get("Location", ""), "code")

    # Step 7: IDP Token
    res = requests.post(
        f"https://fidm.eu1.gigya.com/oidc/op/v1.0/{gigya_key}/token",
        headers={
            "User-Agent": token_agent,
            "Authorization": auth_header,
            "Content-Type": "application/x-www-form-urlencoded",
        },
        data={"code": code, "grant_type": "authorization_code", "redirect_uri": "https://google.it"},
    ).json()
    idp_token = res["access_token"]

    # Step 8: Exchange for Ayla
    res = requests.post(
        "https://user-field-eu.aylanetworks.com/api/v1/token_sign_in",
        headers={"User-Agent": token_agent},
        data={"app_id": app_id, "app_secret": app_secret, "token": idp_token},
    ).json()

    return CloudToken(res["refresh_token"])
