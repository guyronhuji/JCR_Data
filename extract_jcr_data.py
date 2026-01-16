
import sys
import json
import time
import re
import urllib.parse
from playwright.sync_api import sync_playwright
from journal_shortname_resolver import get_journal_shortname

def get_jcr_data(journal_name):
    with sync_playwright() as p:
        launch_args = {
            "headless": True,
            "args": ["--no-sandbox", "--disable-blink-features=AutomationControlled"]
        }
        # Check for explicit executable path (useful for frozen app)
        import os
        exec_path = os.environ.get("PLAYWRIGHT_CHROMIUM_EXECUTABLE_PATH")
        if exec_path and os.path.exists(exec_path):
            launch_args["executable_path"] = exec_path
            
        browser = p.chromium.launch(**launch_args)
        context = browser.new_context(
            user_agent="Mozilla/5.0 (Macintosh; Intel Mac OS X 10_15_7) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/120.0.0.0 Safari/537.36",
            viewport={"width": 1280, "height": 720}
        )
        page = context.new_page()
        
        current_year = 2025
        latest_year = None
        
        print(f"Checking for latest available year for '{journal_name}'...", file=sys.stderr)
        encoded_name = urllib.parse.quote(journal_name)
        
        for year in range(current_year, 2019, -1):
            url = f"https://jcr.clarivate.com/jcr-jp/journal-profile?journal={encoded_name}&year={year}&fromPage=%2Fjcr%2Fhome"
            try:
                print(f"Navigating to {url}...", file=sys.stderr)
                page.goto(url, wait_until="networkidle", timeout=45000)
                try:
                    cookie_btn = page.locator("button#onetrust-accept-btn-handler, button:has-text('Accept All'), button:has-text('Allow all')").first
                    if cookie_btn.is_visible(timeout=5000):
                        cookie_btn.click()
                        time.sleep(2)
                except:
                    pass

                try:
                    page.wait_for_selector(".jif-section, p.title, .metric-value", timeout=15000)
                    latest_year = year
                    break
                except:
                    print(f"Timeout waiting for content on {year}", file=sys.stderr)
                    continue
            except:
                 pass
        
        if not latest_year:
            print("Could not find any valid data.", file=sys.stderr)
            browser.close()
            return None

        metrics = {
            "journal": journal_name,
            "year": latest_year,
            "jif": "N/A",
            "five_year_jif": "N/A",
            "jif_percentile": "N/A"
        }

        try:
            jif_val_el = page.locator("div.jif-values p.value").first
            if jif_val_el.is_visible():
                 metrics["jif"] = jif_val_el.inner_text().strip()

            five_year_el = page.locator("p.five-yr-impact-factor-value").first
            if five_year_el.is_visible():
                 metrics["five_year_jif"] = five_year_el.inner_text().strip()
        except Exception as e:
            print(f"Error metrics: {e}", file=sys.stderr)

        def extract_carousel_data(section_title, stopper_title=None, expand_history=True, metric_name="JIF"):
            rankings_data = {}
            processed_cats = set()
            
            print(f"Extracting data for section: '{section_title}'", file=sys.stderr)
            
            header = page.locator(f"xpath=//*[contains(text(), '{section_title}')]").first
            if not header.is_visible():
                print(f"Header '{section_title}' not found.", file=sys.stderr)
                return {}
            
            header.scroll_into_view_if_needed()
            time.sleep(2)
            
            header_handle = header.element_handle()
            if not header_handle:
                 print("Error: Could not get header handle", file=sys.stderr)
                 return {}
            
            try:
                page.wait_for_selector(".category-value", timeout=5000)
            except:
                pass

            stopper_exists = False
            stopper_handle = None
            if stopper_title:
                s_locator = page.locator(f"xpath=//*[contains(text(), '{stopper_title}')]").first
                if s_locator.is_visible():
                    stopper_exists = True
                    stopper_handle = s_locator.element_handle()
            
            for i in range(15):
                cat_els = page.locator(".category-value").all()
                cat_texts = [c.inner_text().strip() for c in cat_els]
                print(f"Iteration {i}: found {len(cat_texts)} cats.", file=sys.stderr)
                
                relevant_indices = []
                for idx, cat_el in enumerate(cat_els):
                    cat_name = cat_texts[idx]
                    if not cat_name: continue
                    
                    is_valid = True
                    try:
                        # Follows Header
                        pos = cat_el.evaluate("(node, header) => header.compareDocumentPosition(node)", header_handle)
                        if (pos & 4) == 0:
                            is_valid = False
                    except:
                        is_valid = False
                    
                    if is_valid and stopper_exists and stopper_handle:
                         try:
                             # Precedes Stopper
                             pos_stop = cat_el.evaluate("(node, stopper) => stopper.compareDocumentPosition(node)", stopper_handle)
                             if (pos_stop & 2) == 0:
                                is_valid = False
                         except:
                             is_valid = False
                    
                    if is_valid:
                        relevant_indices.append(idx)
                
                if not relevant_indices:
                     pass
                
                found_new_data = False
                
                # Check for JCI sibling data parsing first
                if metric_name == "JCI":
                    for idx in relevant_indices:
                        cat_name = cat_texts[idx]
                        if cat_name in processed_cats: continue
                        
                        cat_el = cat_els[idx]
                        
                        # Look for sibling containing "JCR YEAR"
                        siblings = cat_el.locator("xpath=following-sibling::*").all()
                        jci_text = ""
                        for sib in siblings[:3]:
                            try:
                                txt = sib.inner_text()
                                if "JCR YEAR" in txt or "JCI PERCENTILE" in txt:
                                    jci_text = txt
                                    break
                            except: pass
                        
                        if jci_text:
                            # Parse with RegEx
                            matches = re.findall(r"(\d{4})\s+(\S+)\s+(\S+)\s+(\S+)", jci_text)
                            if matches:
                                c_rows = []
                                for m in matches:
                                    c_rows.append({
                                        "year": int(m[0]),
                                        "rank": m[1],
                                        "quartile": m[2],
                                        "percentile": m[3]
                                    })
                                
                                unique_history = {h['year']: h for h in c_rows}
                                sorted_hist = sorted(unique_history.values(), key=lambda x: x['year'], reverse=True)
                                rankings_data[cat_name] = sorted_hist
                                processed_cats.add(cat_name)
                                found_new_data = True
                                print(f"  Extracted {len(sorted_hist)} years (Sibling Text) for {cat_name}", file=sys.stderr)
                    
                    if found_new_data:
                         pass

                # If not JCI or failed to find sibling, try logic for JIF (Expansion + Table)
                if metric_name == "JIF" or (metric_name == "JCI" and not found_new_data and relevant_indices):
                     
                    if expand_history and relevant_indices:
                        for idx in relevant_indices:
                            cat_el = cat_els[idx]
                            metric_tag = "JIF" if metric_name == "JIF" else "JCI"
                            expand_link = cat_el.locator(f"xpath=following::strong[contains(text(), 'Rank by {metric_tag} before')]").first
                            if expand_link.is_visible():
                                try:
                                    expand_link.click(force=True)
                                    time.sleep(2.0)
                                except:
                                    pass
                            else:
                                expand_link_a = cat_el.locator(f"xpath=following::a[contains(., 'Rank by {metric_tag} before')]").first
                                if expand_link_a.is_visible():
                                    try:
                                        expand_link_a.click(force=True)
                                        time.sleep(2.0)
                                    except:
                                        pass
                        time.sleep(2)

                    for idx in relevant_indices:
                        cat_name = cat_texts[idx]
                        if cat_name in processed_cats: continue
                        
                        cat_el = cat_els[idx]
                        next_cat_el = cat_els[idx+1] if idx < len(cat_els) - 1 else None
                        
                        candidate_tables = cat_el.locator("xpath=following::div[contains(@class, 'scroll-it')]").all()
                        my_tables = []
                        for tbl in candidate_tables[:5]: 
                            is_ours = True
                            if stopper_exists and stopper_handle:
                                 try:
                                     tbl_handle = tbl.element_handle()
                                     if tbl_handle:
                                         pos_t = tbl_handle.evaluate("(node, stopper) => stopper.compareDocumentPosition(node)", stopper_handle)
                                         if (pos_t & 2) == 0:
                                             is_ours = False
                                 except: pass
                            if is_ours and next_cat_el:
                                try:
                                    next_handle = next_cat_el.element_handle()
                                    tbl_handle = tbl.element_handle()
                                    if next_handle and tbl_handle:
                                        pos_l = next_handle.evaluate("(next_cat, table) => next_cat.compareDocumentPosition(table)", tbl_handle)
                                        if (pos_l & 2) == 0:
                                            is_ours = False
                                except: pass
                            if is_ours:
                                my_tables.append(tbl)
                            else:
                                break
                        
                        c_rows = []
                        for tbl in my_tables:
                             try:
                                tbl.evaluate("el => el.scrollTo(0, 10000)")
                                time.sleep(0.1)
                             except: pass
                             rows = tbl.locator("tr").all()
                             for row in rows:
                                cells = row.locator("td").all()
                                if len(cells) >= 4:
                                    year_text = cells[0].text_content().strip()
                                    if year_text.isdigit() and len(year_text) == 4:
                                        c_rows.append({
                                            "year": int(year_text),
                                            "rank": cells[1].text_content().strip(),
                                            "quartile": cells[2].text_content().strip(),
                                            "percentile": cells[3].text_content().strip()
                                        })
                        if c_rows:
                            unique_history = {h['year']: h for h in c_rows}
                            sorted_hist = sorted(unique_history.values(), key=lambda x: x['year'], reverse=True)
                            rankings_data[cat_name] = sorted_hist
                            processed_cats.add(cat_name)
                            found_new_data = True
                            print(f"  Extracted {len(sorted_hist)} years for {cat_name}", file=sys.stderr)

                next_btn = header.locator("xpath=following::*[contains(@class, 'next') or @title='Next button']").first
                if next_btn and next_btn.is_visible():
                    try:
                        next_btn.evaluate("el => el.click()")
                        time.sleep(3)
                        new_cat_els = page.locator(".category-value").all()
                        new_texts = [c.inner_text().strip() for c in new_cat_els]
                        if set(new_texts) == set(cat_texts): 
                             break
                    except:
                        pass
                else:
                    break
                
                if not found_new_data and i > 2:
                     break
            
            return rankings_data

        jif_rankings = extract_carousel_data("Rank by Journal Impact Factor", stopper_title="Rank by Journal Citation Indicator (JCI)", expand_history=True, metric_name="JIF")
        jci_rankings = extract_carousel_data("Rank by Journal Citation Indicator (JCI)", stopper_title="Contributions by Organization", expand_history=True, metric_name="JCI")
        
        browser.close()
        
        if metrics["jif_percentile"] == "N/A" and jif_rankings:
             first_cat = list(jif_rankings.keys())[0]
             for item in jif_rankings[first_cat]:
                if item["year"] == metrics["year"]:
                    metrics["jif_percentile"] = item["percentile"]
                    break

        return {
            "metrics": metrics,
            "rankings": jif_rankings,
            "jci_rankings": jci_rankings
        }

def save_csv(data, filename):
    import csv
    with open(filename, 'w', newline='', encoding='utf-8') as f:
        writer = csv.writer(f)
        writer.writerow(["Journal", "Metric Type", "Category", "Year", "Rank", "Quartile", "Percentile"])
        journal = data["metrics"]["journal"]
        for cat, rows in data.get("rankings", {}).items():
            for row in rows:
                writer.writerow([journal, "JIF", cat, row["year"], row["rank"], row["quartile"], row["percentile"]])
        for cat, rows in data.get("jci_rankings", {}).items():
            for row in rows:
                writer.writerow([journal, "JCI", cat, row["year"], row["rank"], row["quartile"], row["percentile"]])
    print(f"CSV saved to {filename}", file=sys.stderr)

if __name__ == "__main__":
    raw_target = " ".join(sys.argv[1:]) if len(sys.argv) > 1 else "BIOETHICS"
    
    # 1. Try to resolve the short name if it looks like a full title or has spaces
    resolved_target = None
    try:
        resolved_target = get_journal_shortname(raw_target)
    except AssertionError as e:
        print(f"Resolution failed: {e}", file=sys.stderr)
    except Exception as e:
        print(f"Resolution error: {e}", file=sys.stderr)
    
    if resolved_target:
        print(f"Using resolved short name: '{resolved_target}'", file=sys.stderr)
        final_target = resolved_target
    else:
        print(f"Falling back to original name: '{raw_target}'", file=sys.stderr)
        final_target = raw_target

    data = get_jcr_data(final_target)
    if data:
        print(json.dumps(data, indent=2))
        # Save validation check: use final_target for filename
        save_csv(data, f"{final_target}_jcr_data.csv")
