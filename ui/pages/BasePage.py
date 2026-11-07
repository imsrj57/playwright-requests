import os
import shutil
import allure
import time
import asyncio
from datetime import datetime, timedelta
from playwright.async_api import TimeoutError as PlaywrightTimeoutError, expect


class BasePage:
    def __init__(self, driver_manager):
        self.driver_manager = driver_manager
        self.context = None
        self.page = None

    # ---------------------- Page Setup ----------------------
    async def init_page(self):
        self.context = self.driver_manager.context
        if self.context is None:
            raise RuntimeError("Driver context not initialized. Call driver_manager.start() first.")
        self.page = await self.context.new_page()

    async def reopen(self):
        await self.driver_manager.reopen()
        await self.init_page()

    # ---------------------- Network & DOM Waits ----------------------
    async def wait_until_network_idle(self, timeout: int = 10000):
        try:
            await self.page.wait_for_load_state("networkidle", timeout=timeout)
        except PlaywrightTimeoutError:
            print("[Warning] Network idle timeout exceeded.")

    async def wait_for_dom_stability(self, selector: str = None, stable_time: int = 1000, timeout: int = 10000):
        try:
            await self.wait_until_network_idle(timeout=timeout)

            if selector:
                locator = self.page.locator(selector)
                await locator.wait_for(state="visible", timeout=timeout)

                prev_text = await locator.inner_text()
                stable_since = time.time()

                while time.time() - stable_since < (stable_time / 1000):
                    await self.page.wait_for_timeout(200)
                    current_text = await locator.inner_text()
                    if current_text != prev_text:
                        prev_text = current_text
                        stable_since = time.time()
                return True
            else:
                prev_html = await self.page.content()
                stable_since = time.time()
                while time.time() - stable_since < (stable_time / 1000):
                    await self.page.wait_for_timeout(200)
                    current_html = await self.page.content()
                    if current_html != prev_html:
                        prev_html = current_html
                        stable_since = time.time()
                return True
        except Exception as e:
            print(f"[Warning] DOM stability check failed: {e}")
            return False

    # ---------------------- Screenshot Handling ----------------------
    async def take_screenshot(self, name="screenshot"):
        date_str = datetime.now().strftime("%Y-%m-%d")
        base_dir = os.path.join(os.getcwd(), "screenshots", date_str)
        run_count = 1
        while os.path.exists(os.path.join(base_dir, f"{run_count:02d}")):
            run_count += 1
        run_folder = os.path.join(base_dir, f"{run_count:02d}")
        os.makedirs(run_folder, exist_ok=True)

        timestamp = time.strftime("%H%M%S")
        screenshot_filename = f"{name}_{timestamp}.png"
        screenshot_path = os.path.join(run_folder, screenshot_filename)

        await self.page.screenshot(path=screenshot_path, full_page=True)
        allure.attach.file(screenshot_path, name=name, attachment_type=allure.attachment_type.PNG)
        self.cleanup_old_screenshots(days_to_keep=3)

    def cleanup_old_screenshots(self, days_to_keep=3):
        screenshots_dir = os.path.join(os.getcwd(), "screenshots")
        if not os.path.exists(screenshots_dir):
            return
        cutoff_date = datetime.now() - timedelta(days=days_to_keep)
        for folder in os.listdir(screenshots_dir):
            folder_path = os.path.join(screenshots_dir, folder)
            try:
                folder_date = datetime.strptime(folder, "%Y-%m-%d")
                if folder_date < cutoff_date:
                    shutil.rmtree(folder_path)
            except ValueError:
                continue

    async def attach_screenshot(self, name="Screenshot"):
        screenshot_bytes = await self.page.screenshot(full_page=True)
        allure.attach(screenshot_bytes, name=name, attachment_type=allure.attachment_type.PNG)

    # ---------------------- Core Actions (auto-scroll) ----------------------
    async def click_element(self, by_locator, wait_for_idle=True, scroll=True):
        try:
            if wait_for_idle:
                await self.wait_until_network_idle()
            locator = self.page.locator(by_locator)
            await locator.wait_for(state="visible", timeout=30000)
            if scroll:
                await locator.scroll_into_view_if_needed()
            await locator.click()
            if wait_for_idle:
                await self.wait_for_dom_stability()
            return True
        except Exception as e:
            print(f"[Error] click_element failed for {by_locator}: {e}")
            return False

    async def input_element(self, by_locator, text, wait_for_idle=True, scroll=True):
        try:
            if wait_for_idle:
                await self.wait_until_network_idle()
            locator = self.page.locator(by_locator)
            await locator.wait_for(state="visible", timeout=30000)
            if scroll:
                await locator.scroll_into_view_if_needed()
            await locator.fill(text)
            if wait_for_idle:
                await self.wait_for_dom_stability(by_locator)
            return True
        except Exception as e:
            print(f"[Error] input_element failed for {by_locator}: {e}")
            return False

    async def select_dropdown_option(self, by_locator, option_text, wait_for_idle=True, scroll=True):
        try:
            if wait_for_idle:
                await self.wait_for_dom_stability(by_locator)
            if scroll:
                await self.page.locator(by_locator).scroll_into_view_if_needed()
            await self.page.select_option(by_locator, label=option_text)
            if wait_for_idle:
                await self.wait_for_dom_stability()
            return True
        except Exception as e:
            print(f"[Error] select_dropdown_option failed for {by_locator}: {e}")
            return False

    async def selectOptionByvalue(self, by_locator, value, wait_for_idle=True, scroll=True):
        try:
            if wait_for_idle:
                await self.wait_for_dom_stability(by_locator)
            if scroll:
                await self.page.locator(by_locator).scroll_into_view_if_needed()
            await self.page.select_option(by_locator, value=value)
            if wait_for_idle:
                await self.wait_for_dom_stability()
            return True
        except Exception as e:
            print(f"[Error] selectOptionByvalue failed for {by_locator}: {e}")
            return False

    async def auto_suggestion(self, by_locator, text, wait_for_idle=True, scroll=True):
        try:
            if wait_for_idle:
                await self.wait_for_dom_stability(by_locator)
            locator = self.page.locator(by_locator)
            if scroll:
                await locator.scroll_into_view_if_needed()
            await locator.fill(text)
            await locator.press("ArrowDown")
            await locator.press("Enter")
            if wait_for_idle:
                await self.wait_for_dom_stability()
            return True
        except Exception:
            return False

    async def enter_element(self, by_locator, wait_for_idle=True, scroll=True):
        try:
            if wait_for_idle:
                await self.wait_for_dom_stability(by_locator)
            locator = self.page.locator(by_locator)
            if scroll:
                await locator.scroll_into_view_if_needed()
            await locator.press("Enter")
            if wait_for_idle:
                await self.wait_for_dom_stability()
            return True
        except Exception:
            return False

    async def send_data(self, by_locator, data, wait_for_idle=True, scroll=True):
        try:
            if wait_for_idle:
                await self.wait_for_dom_stability(by_locator)
            locator = self.page.locator(by_locator)
            if scroll:
                await locator.scroll_into_view_if_needed()
            await locator.type(data)
            if wait_for_idle:
                await self.wait_for_dom_stability()
            return True
        except Exception as e:
            print(f"[Error] send_data failed for {by_locator}: {e}")
            return False

    # ---------------------- Value/Visibility Helpers ----------------------
    async def get_element_text(self, by_locator, wait_for_idle=True):
        try:
            if wait_for_idle:
                await self.wait_for_dom_stability(by_locator)
            return await self.page.inner_text(by_locator)
        except Exception:
            return ""

    async def getElementValue(self, by_locator):
        try:
            return await self.page.input_value(by_locator)
        except Exception:
            return ""

    async def getTextboxtext(self, by_locator):
        return await self.getElementValue(by_locator)

    async def get_title(self):
        return await self.page.title()

    async def get_element_attribute(self, by_locator, attribute_name, wait_for_idle=True):
        try:
            if wait_for_idle:
                await self.wait_for_dom_stability(by_locator)
            return await self.page.get_attribute(by_locator, attribute_name)
        except Exception as e:
            print(f"[Error] get_element_attribute failed for {by_locator}: {e}")
            return None

    async def verify_element_displayed(self, by_locator, wait_for_idle=True):
        try:
            if wait_for_idle:
                await self.wait_for_dom_stability(by_locator)
            await self.page.locator(by_locator).wait_for(state="visible", timeout=30000)
            return True
        except PlaywrightTimeoutError:
            return False

    async def clear_element(self, by_locator, wait_for_idle=True, scroll=True):
        try:
            if wait_for_idle:
                await self.wait_for_dom_stability(by_locator)
            if scroll:
                await self.page.locator(by_locator).scroll_into_view_if_needed()
            await self.page.locator(by_locator).fill("")
            if wait_for_idle:
                await self.wait_for_dom_stability()
            return True
        except Exception as e:
            print(f"[Error] clear_element failed for {by_locator}: {e}")
            return False

    async def is_element_visible(self, by_locator, timeout=30000):
        try:
            await self.page.locator(by_locator).wait_for(state="visible", timeout=timeout)
            return True
        except PlaywrightTimeoutError:
            return False

    async def scroll_to_element(self, by_locator):
        try:
            await self.page.locator(by_locator).scroll_into_view_if_needed()
        except Exception:
            pass

    # ---------------------- Select first available option ----------------------
    async def select_first_visible_option(self, dropdown_selector, wait_for_idle=True, scroll=True):
        """
        Selects the first option with a non-empty, non-"null" value (skips placeholders).
        """
        try:
            if wait_for_idle:
                await self.wait_for_dom_stability(dropdown_selector)
            locator = self.page.locator(dropdown_selector)
            if scroll:
                await locator.scroll_into_view_if_needed()
            await locator.wait_for(state="visible", timeout=15000)

            # Get all options
            options = await locator.locator("option").all()
            for option in options:
                value = await option.get_attribute("value")
                if value and value.strip() and value.lower() != "null":
                    await locator.select_option(value=value)
                    await asyncio.sleep(0.5)  # brief wait for UI update
                    return True
            return False
        except Exception as e:
            print(f"[Error] select_first_visible_option failed for {dropdown_selector}: {e}")
            return False

    # ---------------------- Loader / Misc ----------------------
    async def wait_for_loader(self, selector: str = ".loading", timeout: int = 30000):
        """Wait for a loader/spinner overlay to appear (briefly) and then disappear."""
        try:
            await self.page.wait_for_selector(selector, state="visible", timeout=2000)
        except PlaywrightTimeoutError:
            return  # loader never appeared
        try:
            await self.page.wait_for_selector(selector, state="hidden", timeout=timeout)
        except PlaywrightTimeoutError:
            print(f"[Warning] loader '{selector}' still visible after {timeout} ms")

    # ---------------------- Navigation ----------------------
    async def goto(self, url: str, wait_until: str = "domcontentloaded"):
        await self.page.goto(url, wait_until=wait_until)

    async def expect_url_contains(self, fragment: str, timeout: int = 30000):
        import re
        await expect(self.page).to_have_url(re.compile(f".*{re.escape(fragment)}.*"), timeout=timeout)
