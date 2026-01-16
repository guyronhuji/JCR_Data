
import sys
import time
import urllib.parse
from playwright.sync_api import sync_playwright

class JCRBackend:
    def __init__(self):
        self.playwright = None
        self.browser = None
        self.context = None
        self.page = None

    def start_session(self):
        """Launches the browser and navigates to JCR home."""
        print("Initializing JCR Session (headless browser)...", file=sys.stderr)
        self.playwright = sync_playwright().start()
        
        launch_args = {
            "headless": True,
            "args": ["--no-sandbox", "--disable-blink-features=AutomationControlled"]
        }
        
        import os
        exec_path = os.environ.get("PLAYWRIGHT_CHROMIUM_EXECUTABLE_PATH")
        if exec_path and os.path.exists(exec_path):
            launch_args["executable_path"] = exec_path
            
        self.browser = self.playwright.chromium.launch(**launch_args)
        self.context = self.browser.new_context(
            user_agent="Mozilla/5.0 (Macintosh; Intel Mac OS X 10_15_7) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/120.0.0.0 Safari/537.36",
            viewport={"width": 1280, "height": 720}
        )
        self.page = self.context.new_page()
        try:
            self.page.goto("https://jcr.clarivate.com/jcr/home", wait_until="networkidle", timeout=60000)
            # Handle cookie banner if present
            try:
                cookie_btn = self.page.locator("button#onetrust-accept-btn-handler, button:has-text('Accept All')").first
                if cookie_btn.is_visible(timeout=5000):
                    cookie_btn.click()
            except:
                pass
        except Exception as e:
            raise Exception(f"Failed to load JCR home: {e}")

    def search_journal(self, query):
        """Enters query and returns a list of suggested journal names."""
    def search_journal(self, query):
        """Enters query and returns a list of suggested journal names."""
        if not self.page:
            self.start_session()
        else:
            # unique check to avoid reloading if we are already there and ready, 
            # but simpler to just reload to be safe and clear state
            try:
                if "jcr/home" not in self.page.url:
                    self.page.goto("https://jcr.clarivate.com/jcr/home", wait_until="networkidle", timeout=30000)
                else:
                    # Even if on home, sometimes good to reload or ensure input is clear
                    # But finding the input should handle it.
                    pass
            except:
                # If check fails, try force goto
                self.page.goto("https://jcr.clarivate.com/jcr/home", wait_until="networkidle", timeout=30000)
            
        print(f"Searching for '{query}'...", file=sys.stderr)
        # Locate search input
        search_input = self.page.locator("input[placeholder*='journal'], input[placeholder*='Journal'], input[type='text'].mat-input-element").first
        if not search_input.is_visible():
            raise Exception("Search input not found")
            
        search_input.click()
        search_input.fill("")
        search_input.fill(query)
        
        # Wait specifically for the specific autocomplete dropdown items
        try:
            self.page.wait_for_selector(".journal-title, mat-option span", timeout=5000)
        except:
            # If no suggestions appear, return empty
            return []
            
        options = self.page.locator(".journal-title, mat-option span.highlight-text, mat-option span").all()
        
        results = []
        seen = set()
        for opt in options:
            txt = opt.inner_text().strip()
            if txt and txt not in seen:
                results.append(txt)
                seen.add(txt)
        return results

    def select_and_resolve(self, journal_name):
        """Clicks the exact journal name and extracts short name from URL."""
        print(f"Resolving short name for '{journal_name}'...", file=sys.stderr)
        
        # Find the specific option again to click it
        options = self.page.locator(".journal-title, mat-option span").all()
        target_opt = None
        
        for opt in options:
            if opt.inner_text().strip() == journal_name:
                target_opt = opt
                break
        
        if not target_opt:
            raise Exception(f"Option '{journal_name}' no longer found.")
            
        # Try to detect new page or navigation
        new_page = None
        navigated = False
        
        # Check for new page event
        try:
            with self.context.expect_page(timeout=5000) as page_info:
                # Primary click
                try:
                    target_opt.click(timeout=2000)
                except:
                    target_opt.click(force=True)
            new_page = page_info.value
        except:
            # No new page detected immediately
            pass

        if new_page:
            self.page = new_page
            self.page.wait_for_load_state()
            navigated = True
        else:
             # Check if we navigated in current page
             try:
                 self.page.wait_for_url(lambda u: "journal-profile" in u, timeout=5000)
                 navigated = True
             except:
                 pass
        
        if not navigated:
             print("Click failed or no nav, trying keyboard fallback...", file=sys.stderr)
             try:
                 search_input = self.page.locator("input[placeholder*='journal'], input[placeholder*='Journal'], input[type='text'].mat-input-element").first
                 search_input.click()
                 search_input.fill(journal_name)
                 time.sleep(2)
                 self.page.keyboard.press("ArrowDown")
                 time.sleep(0.5)
                 
                 # Expect new page on Enter?
                 try:
                     with self.context.expect_page(timeout=5000) as page_info:
                         self.page.keyboard.press("Enter")
                     new_page = page_info.value
                     if new_page:
                         self.page = new_page
                         self.page.wait_for_load_state()
                         navigated = True
                 except:
                     # Maybe SPA nav
                     self.page.keyboard.press("Enter")
                     try:
                         self.page.wait_for_url(lambda u: "journal-profile" in u, timeout=10000)
                         navigated = True
                     except:
                         pass
             except Exception as e:
                 print(f"Keyboard fallback error: {e}", file=sys.stderr)

        # Final wait/check
        if not navigated:
             # Check for any new pages that might have appeared silently
             if len(self.context.pages) > 1:
                 # Switch to the latest page
                 self.page = self.context.pages[-1]
                 self.page.wait_for_load_state()
                 if "journal-profile" in self.page.url:
                     navigated = True

        if not navigated:
             try:
                 self.page.wait_for_url(lambda u: "journal-profile" in u, timeout=20000)
             except:
                  if "search-results" in self.page.url:
                      pass
                  raise Exception("Navigation to journal profile failed (timeout).")
            
        # Extract
        current_url = self.page.url
        parsed = urllib.parse.urlparse(current_url)
        params = urllib.parse.parse_qs(parsed.query)
        
        if "journal" in params:
            return params["journal"][0]
        else:
            raise Exception("Could not find 'journal' parameter in URL.")

    def close(self):
        if self.browser:
            self.browser.close()
        if self.playwright:
            self.playwright.stop()

def main():
    backend = JCRBackend()
    try:
        backend.start_session()
        print("\n=== JCR Search CLI ===")
        
        while True:
            print("\nEnter a journal name (or 'q' to quit):")
            query = input("> ").strip()
            
            if query.lower() == 'q':
                break
            
            if not query:
                continue
                
            try:
                results = backend.search_journal(query)
                
                if not results:
                    print("No results found.")
                    continue
                
                print(f"\nFound {len(results)} results:")
                for i, res in enumerate(results):
                    print(f"{i+1}. {res}")
                
                print("\nSelect a number to resolve (or 'c' to cancel):")
                selection = input("> ").strip()
                
                if selection.lower() == 'c':
                    continue
                
                if not selection.isdigit() or int(selection) < 1 or int(selection) > len(results):
                    print("Invalid selection.")
                    continue
                
                selected_journal = results[int(selection) - 1]
                
                short_name = backend.select_and_resolve(selected_journal)
                print(f"\n✅ RESULT: {selected_journal} -> {short_name}")
                
            except Exception as e:
                print(f"Error: {e}")
                
    except KeyboardInterrupt:
        print("\nExiting...")
    except Exception as e:
        print(f"Fatal Error: {e}")
    finally:
        print("Closing browser session...")
        backend.close()

if __name__ == "__main__":
    main()
