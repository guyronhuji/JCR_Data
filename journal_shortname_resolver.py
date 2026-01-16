
import sys
import time
import urllib.parse
from playwright.sync_api import sync_playwright

def get_journal_shortname(journal_name):
    """
    Navigates to the JCR homepage, searches for the given journal name,
    clicks the exact match, and returns the journal short name from the URL.

    Raises:
        AssertionError: If no exact match is found or navigation fails.
    """
    print(f"Resolving short name for '{journal_name}'...", file=sys.stderr)
    
    with sync_playwright() as p:
        # Launch browser with explicit path check
        import os
        launch_args = {
            "headless": True,
            "args": ["--no-sandbox", "--disable-blink-features=AutomationControlled"]
        }
        exec_path = os.environ.get("PLAYWRIGHT_CHROMIUM_EXECUTABLE_PATH")
        if exec_path and os.path.exists(exec_path):
            launch_args["executable_path"] = exec_path

        browser = p.chromium.launch(**launch_args)
        context = browser.new_context(
            user_agent="Mozilla/5.0 (Macintosh; Intel Mac OS X 10_15_7) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/120.0.0.0 Safari/537.36",
            viewport={"width": 1280, "height": 720}
        )
        page = context.new_page()
        
        try:
            # Navigate to JCR home
            page.goto("https://jcr.clarivate.com/jcr/home", wait_until="networkidle", timeout=45000)
            
            # Handle cookies (optional but good practice)
            try:
                cookie_btn = page.locator("button#onetrust-accept-btn-handler, button:has-text('Accept All'), button:has-text('Allow all')").first
                if cookie_btn.is_visible(timeout=5000):
                    cookie_btn.click()
                    time.sleep(1)
            except:
                pass
            
            # Locate search input
            search_input = page.locator("input[placeholder*='journal'], input[placeholder*='Journal'], input[type='text'].mat-input-element").first
            
            if not search_input.is_visible():
                raise AssertionError("Could not find search box on JCR Home page.")

            # Type journal name
            search_input.click()
            search_input.fill(journal_name)
            
            # Wait for autocomplete suggestions
            # We assume a slight delay is needed for the list to populate
            time.sleep(3)
            
            # Find the option with EXACT match
            # Confirmed HTML: <p class="pop-content journal-title"><span class="highlight-text">Feminist Anthropology</span></p>
            # The container is likely .pop-content.journal-title or just .journal-title
            
            try:
                page.wait_for_selector(".journal-title", timeout=10000)
            except:
                pass

            options = page.locator(".journal-title, .search-result-item, mat-option span").all()
            
            target_option = None
            found_text = ""
            
            print(f"DEBUG: Found {len(options)} potential options.", file=sys.stderr)

            for opt in options:
                # Visibility check might be tricky if it's hidden/overlapped, but usually works
                # if not opt.is_visible(): continue 
                
                # Clean text: remove newlines/spaces
                txt = opt.inner_text().strip()
                print(f"DEBUG: Option text: '{txt}'", file=sys.stderr)
                
                # Check for exact match (case-insensitive)
                if txt.lower() == journal_name.lower():
                    target_option = opt
                    found_text = txt
                    break
            
            if not target_option:
                # If no exact match found in list, we ASSERT ERROR as requested
                raise AssertionError(f"No exact match found for journal '{journal_name}' in search suggestions.")
            
            print(f"Found match: '{found_text}'. Clicking...", file=sys.stderr)
            
            # Try clicking the parent p tag if we have the span, or just the element itself
            try:
                # Ensure we click the interactive part. The p tag had tabindex=0
                target_option.click(timeout=2000)
            except:
                print("Standard click failed, trying force click...", file=sys.stderr)
                target_option.click(force=True)
            
            # Wait for navigation to start
            time.sleep(2)
            
            # Fallback: if URL hasn't changed to include 'journal-profile', try keyboard navigation
            if "journal-profile" not in page.url:
                 print("Click didn't trigger navigation, trying Keyboard (ArrowDown + Enter)...", file=sys.stderr)
                 # Focus input again just in case
                 search_input.focus()
                 page.keyboard.press("ArrowDown")
                 time.sleep(0.5)
                 page.keyboard.press("Enter")
            
            # Wait for navigation to journal profile OR search results
            try:
                page.wait_for_url(lambda u: "journal-profile" in u or "search-results" in u, timeout=30000)
            except:
                 raise AssertionError(f"Navigation failed or timed out. Current URL: {page.url}")

            # Check if we are on search results
            if "search-results" in page.url:
                print("Landed on Search Results page. Finding journal link...", file=sys.stderr)
                try:
                    # Wait for results to load
                    page.wait_for_selector(".table-cell-journalName", timeout=15000)
                    
                    # Find link using text match
                    # The result item is a span with class table-cell-journalName
                    res_links = page.locator(".table-cell-journalName").all()
                    
                    target_link = None
                    for link in res_links:
                        if link.is_visible() and link.inner_text().strip().lower() == journal_name.lower():
                            target_link = link
                            break
                    
                    if target_link:
                        print(f"Found result link. Clicking...", file=sys.stderr)
                        
                        # Handle potential new tab
                        with context.expect_page(timeout=10000) as new_page_info:
                             target_link.click()
                        
                        try:
                            new_page = new_page_info.value
                            print("New tab opened. Switching context...", file=sys.stderr)
                            new_page.wait_for_load_state()
                            page = new_page
                        except:
                            # No new page, assume SPA navigation
                            print("No new tab, assuming SPA navigation...", file=sys.stderr)
                            page.wait_for_url(lambda u: "journal-profile" in u, timeout=30000)

                    else:
                        raise AssertionError(f"Journal '{journal_name}' not found on search results page.")

                except Exception as e:
                    raise AssertionError(f"Error handling search results: {e}")

            current_url = page.url
            parsed = urllib.parse.urlparse(current_url)
            params = urllib.parse.parse_qs(parsed.query)
            
            if "journal" in params:
                short_name = params["journal"][0]
                return short_name
            else:
                raise AssertionError(f"Could not extract 'journal' parameter (short name) from URL: {current_url}")
                
        except Exception as e:
            # Re-raise AssertionErrors directly, wrap others
            if isinstance(e, AssertionError):
                raise e
            raise AssertionError(f"An unexpected error occurred: {e}")
        finally:
            browser.close()

if __name__ == "__main__":
    if len(sys.argv) > 1:
        j_name = " ".join(sys.argv[1:])
        try:
            sn = get_journal_shortname(j_name)
            print(f"Short Name: {sn}")
        except AssertionError as ae:
            print(f"Error: {ae}")
            sys.exit(1)
    else:
        print("Usage: python journal_shortname_resolver.py <Journal Name>")
