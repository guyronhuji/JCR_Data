
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
        self.known_journals = {} # Cache for "Full Name" -> "Short Key"

    def _handle_response(self, response):
        """Background listener to intercept search API results."""
        try:
            # DEBUG
            # if "jcr" in response.url:
            #     print(f"DEBUG URL: {response.url}", file=sys.stderr)

            # We are looking for JSON responses from search endpoints
            if "search" in response.url.lower() and "json" in response.headers.get("content-type", "").lower():
                try:
                    data = response.json()
                    # print(f"DEBUG: Captured search API response from {response.url}", file=sys.stderr)
                    # print(f"DEBUG DATA: {str(data)[:600]}...", file=sys.stderr) # Truncate 
                    
                    # Actual structure from testing:
                    # { "data": { "journals": [ { "journalName": "FEM ANTHROPOL", "title": "Feminist Anthropology", ... } ] } }

                    items = []
                    if "data" in data and "journals" in data["data"]:
                        items = data["data"]["journals"]
                    
                    for item in items:
                        if isinstance(item, dict):
                            # Try to identify name and key
                            name = item.get("title")
                            key = item.get("journalName") # This is the short key!
                            
                            if name and key:
                                self.known_journals[name.strip()] = key
                                # Also map normalized upper/lower for easier lookup
                                self.known_journals[name.strip().lower()] = key
                except:
                    pass
        except:
            pass

    def _handle_cookie_banner(self):
        """Attempts to close the OneTrust cookie banner if present."""
        try:
            # Common selectors for OneTrust
            selectors = [
                "button#onetrust-accept-btn-handler",
                "button.onetrust-close-btn-handler",
                "button:has-text('Accept All')",
                "button:has-text('Accept Cookies')"
            ]
            for sel in selectors:
                try:
                    btn = self.page.locator(sel).first
                    if btn.is_visible(timeout=500):
                        print("Found cookie banner, clicking accept...", file=sys.stderr)
                        btn.click()
                        self.page.wait_for_timeout(500) # Wait for animation
                        return
                except:
                    pass
        except:
            pass

    def start_session(self):
        """Launches the browser and navigates to JCR home."""
        print("Initializing JCR Session (headless browser)...", file=sys.stderr)
        self.playwright = sync_playwright().start()
        
        launch_args = {
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
        # Hook up the listener
        self.page.on("response", self._handle_response)
        
        try:
            # use domcontentloaded instead of networkidle for speed
            self.page.goto("https://jcr.clarivate.com/jcr/home", wait_until="domcontentloaded", timeout=60000)
            self._handle_cookie_banner()
        except Exception as e:
            raise Exception(f"Failed to load JCR home: {e}")

    def search_journal(self, query):
        """Enters query and returns a list of suggested journal names."""
        # Try to find search input immediately on current page
        search_input_sel = "input[placeholder*='journal'], input[placeholder*='Journal'], input[type='text'].mat-input-element"
        search_input = self.page.locator(search_input_sel).first
        
        if not search_input.is_visible():
            # If not found, then go home
            print("Search bar not found, navigating to home...", file=sys.stderr)
            self.page.goto("https://jcr.clarivate.com/jcr/home", wait_until="domcontentloaded", timeout=30000)
            try:
                self.page.wait_for_selector(search_input_sel, state="visible", timeout=10000)
            except:
                pass # search_input.is_visible check below will handle failure
            search_input = self.page.locator(search_input_sel).first
            
        print(f"Searching for '{query}'...", file=sys.stderr)
        if not search_input.is_visible():
            raise Exception("Search input not found even after reloading home")
            
        self._handle_cookie_banner() # Check again before interaction
        try:
            search_input.click(force=True) # Force through any invisible overlays if possible
        except:
            self._handle_cookie_banner()
            search_input.click(force=True)

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
        
        # FAST TRACK: Check if we already intercepted the key
        if journal_name.strip() in self.known_journals:
            print(" -> Found in API cache! Instant resolve.", file=sys.stderr)
            return self.known_journals[journal_name.strip()]
        if journal_name.strip().lower() in self.known_journals:
            print(" -> Found in API cache! Instant resolve.", file=sys.stderr)
            return self.known_journals[journal_name.strip().lower()]
            
        print(" -> Not in cache, falling back to UI navigation...", file=sys.stderr)
        
        # Find the specific option again to click it
        # We use get_by_text with exact=True to ensure we pick the right one
        try:
            self.page.locator(".journal-title, mat-option span").get_by_text(journal_name, exact=True).first.click()
        except:
            # Fallback for some overlay or detachment
            self.page.locator(".journal-title, mat-option span").get_by_text(journal_name, exact=True).first.click(force=True)

        # Wait for navigation to profile
        try:
            self.page.wait_for_url(lambda u: "journal-profile" in u, timeout=20000)
        except:
             # Just in case we are already there or something went wrong
             if "journal-profile" not in self.page.url:
                 raise Exception("Navigation to journal profile failed after clicking result.")
            
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
