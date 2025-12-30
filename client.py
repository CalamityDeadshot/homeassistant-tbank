"""Selenium + T-Bank client."""

import json
import logging

import requests
from selenium import webdriver
from selenium.common import TimeoutException
from selenium.webdriver.chrome.options import Options
from selenium.webdriver.common.by import By
from selenium.webdriver.support import expected_conditions as EC
from selenium.webdriver.support.ui import WebDriverWait

logger = logging.getLogger("tbank")

class Client():
    """Selenium + T-Bank client."""

    BASE_URL = "https://tbank.ru"

    def __init__(self, selenium, code, user: str) -> None:
        self.selenium_url: str = selenium
        self.code: str = code
        driver_options = Options()
        driver_options.add_argument("--disable-gpu")
        driver_options.add_argument("--window-size=1920,1080")
        driver_options.add_argument("--no-sandbox")
        driver_options.add_argument("--disable-dev-shm-usage")
        driver_options.add_argument(f"--user-data-dir=user-data-{user}")
        self.driver_options = driver_options
        self.driver: webdriver.Remote | None = None

    def testConnection(self) -> bool:
        try:
            logger.info("Testing Selenium connection")
            self.getDriver().get(self.BASE_URL)
        except Exception as e:
            logger.error(f"Selenium connection failed: {e}")
            return False
        else:
            logger.info("Selenium connection established")
            return True
        finally:
            self.cleanup()

    def enter_auth_flow(self):
        try:
            logger.info("Starting Selenium session for authentication.")
            self.getDriver().get(self.BASE_URL)
        except Exception as e:
            logger.error(f"Selenium connection failed: {e}")
            return False
        else:
            logger.info("Selenium connection established")

    def test_access(self) -> bool:
        try:
            self.waitFor(self.getDriver(), "//a[@href='/new-product/']")
        except TimeoutException:
            return False
        else:
            return True
        finally:
            self.cleanup()

    def getDriver(self):
        if self.driver is None:
            self.driver = webdriver.Remote(
                command_executor=self.selenium_url,
                options=self.driver_options
            )
        return self.driver

    def cleanup(self):
        if self.driver is None:
            return
        self.driver.quit()
        self.driver = None

    def debugPrint(self, string):
        logger.info(string)

    def run(self):
        session_id = self.obtainSessionId()
        data = self.tryGetAccounts(session_id)
        return data

    def waitFor(self, driver, xpath):
        WebDriverWait(driver, 60).until(
            EC.presence_of_element_located((By.XPATH, xpath))
        )

    def obtainSessionId(self) -> str | None:
        driver = None
        session_id = None
        try:
            driver = self.getDriver()
            driver.implicitly_wait(30)

            driver.get(f"{self.BASE_URL}/login")
            self.debugPrint(f"Opened {driver.title}")
            # Authenticated hueristic: wait for an element that is only visible when logged in.
            try:
                self.waitFor(driver, "//a[@href='/new-product/']")
            except TimeoutException:
                self.debugPrint("Seems like browser session expired. Trying to input quick login code...")
                self.tryRenewSession(driver)
                self.waitFor(driver, "//a[@href='/new-product/']")

            cookie = driver.get_cookie("psid")

            if cookie:
                self.debugPrint(f"Session id: {cookie["value"]}")
                session_id = cookie["value"]
            else:
                self.debugPrint("Session cookie not found. Fuck.")
                raise SessionError
        finally:
            self.cleanup()

        return session_id

    def tryRenewSession(self, driver: webdriver.Remote):
        self.debugPrint("Trying to input code...")
        for i, char in enumerate(self.code):
            WebDriverWait(driver, 10)\
                .until(EC.visibility_of_element_located((By.XPATH, f"//input[@automation-id='pin-code-input-{i}']")))\
                .send_keys(char)

    def tryGetAccounts(self, session_id: str | None) -> dict:
        if not session_id:
            raise SessionError
        self.debugPrint(f"Session id: {session_id}")

        accountData = self.getBankAccounts(session_id)
        self.debugPrint(json.dumps(accountData))
        self.debugPrint("")

        investmentsData = self.getInvestmentAccounts(session_id)
        self.debugPrint(json.dumps(investmentsData))
        self.debugPrint("")

        totalRub = sum(a["money"]["amount"] for a in filter(lambda a: a["type"] != "Credit" and a["money"]["currency"] == "RUB", accountData)) + sum(a["money"]["amount"] for a in investmentsData)
        totalUsd = sum(a["money"]["amount"] for a in filter(lambda a: a["type"] != "Credit" and a["money"]["currency"] == "USD", accountData))
        self.debugPrint(f"\n Total: {totalRub} RUB, {totalUsd} USD")
        self.debugPrint(json.dumps(investmentsData))
        data = {
            "bank": accountData,
            "investments": investmentsData,
            "totalRub": totalRub
        }
        # print(json.dumps(data))
        return data

    def getBankAccounts(self, session_id: str):
        accounts = requests.get(
            url="https://www.tbank.ru/api/common/v1/accounts_light_ib",
            params={
                "appName": "supreme",
                "appVersion": "0.0.1",
                "platform": "web",
                "sessionid": session_id,
                "origin": "web,ib5,platform"
            },
            timeout=10
        )
        accounts.raise_for_status()

        response = accounts.json()
        if response["resultCode"] == "INSUFFICIENT_PRIVILEGES":
            raise SessionError()

        def accountMapping(account):
            return {
                "name": account["name"],
                "type": account["accountType"],
                "money": {
                    "amount": account["moneyAmount"]["value"],
                    "currency": account["moneyAmount"]["currency"]["name"]
                }
            }

        return list(map(accountMapping, response["payload"]))

    def getInvestmentAccounts(self, session_id: str):
        investments = requests.get(
            url="https://api-invest-gw.tinkoff.ru/invest-portfolio/portfolios/accounts",
            params={
                "sessionid": session_id,
                "currency": "RUB",
                "withInvestBox": True
            },
            headers={
                "X-APP-NAME": "supreme"
            },
            timeout=10
        )
        investments.raise_for_status()
        response = investments.json()
        self.debugPrint(json.dumps(response))

        def investmentMapping(account):
            self.debugPrint(f"Fetching account {account['name']} ({account['brokerAccountId']})")
            is_investbox = account['brokerAccountType'] == "InvestBox"
            positions = self.getInvestmentAccountData(session_id, account["brokerAccountId"]) if not is_investbox else []
            total_amount = account["totalAmount"]["value"] if is_investbox else sum(map(lambda p: p["money"]["RUB"]["total"], positions))
            return {
                "name": account["name"],
                "money": {
                    "amount": total_amount,
                    "currency": account["totalAmount"]["currency"],
                    "positions": positions
                }
            }

        return list(map(investmentMapping, response["accounts"]["list"]))

    def getInvestmentAccountData(self, session_id: str, account_id: str):
        account_request = requests.get(
            url="https://www.tbank.ru/api/invest-gw/invest-portfolio/portfolios/purchased-securities",
            params={
                "sessionId": session_id,
                "currency": "RUB",
                "accountTypes": "tinkoff,tinkoff_iis,dfa",
                "brokerAccountId": account_id
            },
            headers={
                "X-APP-NAME": "invest"
            },
            timeout=10
        )
        account_request.raise_for_status()
        def positionMapping(position):
            current_price = position["pricesByCurrency"]["currentPrice"]
            count = position["currentBalance"]
            display = position["positionParams"]["displayParams"]
            return {
                "ticker": position["ticker"],
                "type": position["securityType"],
                "count": count,
                "money": {
                    "RUB": {
                        "total": current_price["RUB"] * count,
                        "price": current_price["RUB"],
                    },
                    "USD": {
                        "total": current_price["USD"] * count,
                        "price": current_price["USD"],
                    },
                    "EUR": {
                        "total": current_price["EUR"] * count,
                        "price": current_price["EUR"],
                    }
                },
                "display": {
                    "text_color": display["textColor"],
                    "logo_color": display["logoColor"],
                    "name": display["showName"]
                }
            }

        response = account_request.json()
        real_positions = filter(lambda p: p["securityType"] != "virtual_stock", response["portfolios"][0]["positions"])
        return list(map(positionMapping, real_positions))

class SessionError(Exception): ...
