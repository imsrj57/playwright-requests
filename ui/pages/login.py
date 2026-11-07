# ui/pages/login.py
"""
Generic login page object. Override the locators to match your application,
either by editing the defaults below or by subclassing LoginPage.
"""

import allure

from ui.pages.BasePage import BasePage


class LoginPage:
    # --- Locators (adjust for your app) ---
    USERNAME_INPUT = "input[name='username'], input#Username, input[type='email']"
    PASSWORD_INPUT = "input[name='password'], input#Password, input[type='password']"
    SUBMIT_BUTTON = "button[type='submit']"
    # Element that is only visible after a successful login
    LOGGED_IN_INDICATOR = "[data-testid='user-menu'], nav"
    ERROR_MESSAGE = ".error, .alert-danger, [role='alert']"

    def __init__(self, base: BasePage):
        self.base = base

    @allure.step("Open login page")
    async def open(self, url: str):
        await self.base.goto(url)

    @allure.step("Login as {username}")
    async def login(self, url: str, username: str, password: str, expect_success: bool = True):
        await self.open(url)
        await self.base.input_element(self.USERNAME_INPUT, username)
        await self.base.input_element(self.PASSWORD_INPUT, password)
        await self.base.click_element(self.SUBMIT_BUTTON)

        if expect_success:
            if not await self.base.verify_element_displayed(self.LOGGED_IN_INDICATOR):
                await self.base.attach_screenshot("Login Failure")
                raise AssertionError("Login failed — logged-in indicator not visible.")
            await self.base.attach_screenshot("Login Success")

    async def get_error_message(self) -> str:
        return await self.base.get_element_text(self.ERROR_MESSAGE)


async def login(base: BasePage, url: str, username: str, password: str):
    """Functional shortcut: `await login(base, url, user, pwd)`."""
    await LoginPage(base).login(url, username, password)
