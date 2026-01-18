
import customtkinter as ctk
import tkinter as tk # Still needed for some constants or mixins if needed
from tkinter import messagebox, filedialog # CTk messageboxes are different, but we can reuse or switch
import threading
import csv
import os
import sys

# --- CONFIG ---
ctk.set_appearance_mode("System")
ctk.set_default_color_theme("blue")

# CRITICAL: Tell Playwright to look for browsers in the system cache
os.environ["PLAYWRIGHT_BROWSERS_PATH"] = "0"

def find_system_chromium():
    found_executable = None
    home = os.path.expanduser("~")
    possible_roots = []
    
    if sys.platform == "darwin":
        possible_roots = [os.path.join(home, "Library", "Caches", "ms-playwright")]
    elif sys.platform == "linux":
        possible_roots = [os.path.join(home, ".cache", "ms-playwright")]
    elif sys.platform == "win32":
        possible_roots = [os.path.join(home, "AppData", "Local", "ms-playwright")]
        
    for root in possible_roots:
        if os.path.exists(root):
            dirs = [d for d in os.listdir(root) if "chromium" in d and os.path.isdir(os.path.join(root, d))]
            for d in dirs:
                deep_path = os.path.join(root, d)
                for root_deep, _, files in os.walk(deep_path):
                    for file in files:
                        if file in ["Chromium", "chrome", "chrome-headless-shell", "chrome.exe"]:
                            full_path = os.path.join(root_deep, file)
                            if os.access(full_path, os.X_OK): # Check executable permission (mostly for unix)
                                return full_path
    return None

def install_chromium():
    import subprocess
    from playwright._impl._driver import compute_driver_executable
    
    try:
        driver_executable, driver_cli = compute_driver_executable()
        # If frozen, driver_executable might be ok, but let's be safe.
        # Typically compute_driver_executable returns the path to the node executable or python wrapper.
        
        # On PyInstaller, we might need to rely on the fact that 'playwright' module is importable.
        # But we need to RUN the install command.
        
        # Simpler approach: use python -m playwright install chromium
        # BUT we might be in a frozen app without 'python'.
        
        # Using the computed driver executable is the most robust internal way:
        cmd = [driver_executable, "install", "chromium"]
        if sys.platform == "win32":
             # On windows, ensure we don't pop up a window if possible, OR popping up is good so they see it?
             # Let's let it output to stdout/err and we log it?
             pass
             
        subprocess.run(cmd, check=True)
        return True
    except Exception as e:
        with open(log_file, "a") as f: f.write(f"Install failed: {e}\n")
        return False

# --- EXPLICIT PATH OVERRIDE LOGIC ---
try:
    log_file = os.path.join(os.path.expanduser("~"), "jcr_debug.log")
    with open(log_file, "a") as f:
        f.write(f"\n--- App Start ---\n")
        f.write(f"CWD: {os.getcwd()}\n")
        f.write(f"sys.frozen: {getattr(sys, 'frozen', 'Not Set')}\n")
    
    # 1. Try to find
    exe_path = find_system_chromium()
    
    # 2. If not found, install
    if not exe_path:
        with open(log_file, "a") as f: f.write("Chromium not found. Attempting install...\n")
        if install_chromium():
            with open(log_file, "a") as f: f.write("Install finished. Re-scanning...\n")
            exe_path = find_system_chromium()
    
    if exe_path:
        os.environ["PLAYWRIGHT_CHROMIUM_EXECUTABLE_PATH"] = exe_path
        with open(log_file, "a") as f: f.write(f"Forcing Executable: {exe_path}\n")
    else:
        with open(log_file, "a") as f: f.write("Could not find system chromium binary even after install attempt.\n")

except Exception as e:
    try:
        with open(log_file, "a") as f: f.write(f"Error in init logic: {e}\n")
    except:
        pass
# ------------------------------------

# Global placeholders for lazy loaded modules
get_journal_shortname = None
get_jcr_data = None
save_jcr_data_csv = None
calculate_category_averages = None

class ResultListFrame(ctk.CTkScrollableFrame):
    def __init__(self, master, selection_callback, **kwargs):
        super().__init__(master, **kwargs)
        self.selection_callback = selection_callback
        self.buttons = []

    def populate(self, items):
        # Clear existing
        for btn in self.buttons:
            btn.destroy()
        self.buttons = []
        
        for item in items:
            btn = ctk.CTkButton(self, text=item, anchor="w", fg_color="transparent", text_color=("gray10", "gray90"), hover_color=("gray75", "gray25"), command=lambda i=item: self.selection_callback(i))
            btn.pack(fill="x", padx=2, pady=2)
            self.buttons.append(btn)

class JCRApp(ctk.CTk):
    def __init__(self):
        super().__init__()
        self.title("JCR Data Analyzer")
        self.geometry("900x700")
        
        # Main Layout
        self.grid_columnconfigure(0, weight=1)
        self.grid_rowconfigure(1, weight=1) # Results take space
        
        # --- INPUT FRAME ---
        self.input_frame = ctk.CTkFrame(self)
        self.input_frame.grid(row=0, column=0, padx=20, pady=(20, 10), sticky="ew")
        self.input_frame.grid_columnconfigure(1, weight=1)
        
        # Journal Name
        ctk.CTkLabel(self.input_frame, text="Journal Name:").grid(row=0, column=0, padx=10, pady=10, sticky="w")
        self.journal_entry = ctk.CTkEntry(self.input_frame, placeholder_text="e.g. Feminist Anthropology")
        self.journal_entry.grid(row=0, column=1, padx=10, pady=10, sticky="ew")
        
        self.search_btn = ctk.CTkButton(self.input_frame, text="Search", width=100, command=self.run_search)
        self.search_btn.grid(row=0, column=2, padx=10, pady=10)
        
        # Search Results
        self.result_list = ResultListFrame(self.input_frame, selection_callback=self.on_list_select, height=100)
        self.result_list.grid(row=1, column=1, columnspan=2, padx=10, pady=(0, 10), sticky="ew")
        
        # Start Year
        ctk.CTkLabel(self.input_frame, text="Start Year:").grid(row=2, column=0, padx=10, pady=10, sticky="w")
        self.year_entry = ctk.CTkEntry(self.input_frame)
        self.year_entry.insert(0, "2024")
        self.year_entry.grid(row=2, column=1, padx=10, pady=10, sticky="ew")
        
        # Output Directory
        ctk.CTkLabel(self.input_frame, text="Output Dir:").grid(row=3, column=0, padx=10, pady=10, sticky="w")
        self.out_dir_entry = ctk.CTkEntry(self.input_frame)
        default_dir = os.path.join(os.path.expanduser("~"), "Documents", "JCR_Output")
        self.out_dir_entry.insert(0, default_dir)
        self.out_dir_entry.grid(row=3, column=1, padx=10, pady=10, sticky="ew")
        
        self.browse_btn = ctk.CTkButton(self.input_frame, text="Browse", width=100, command=self.browse_dir)
        self.browse_btn.grid(row=3, column=2, padx=10, pady=10)
        
        # Run Button
        self.run_btn = ctk.CTkButton(self.input_frame, text="Get Data & Analyze", command=self.start_process, fg_color="#2CC985", hover_color="#229966") # Greenish
        self.run_btn.grid(row=4, column=0, columnspan=3, padx=20, pady=20, sticky="ew")

        # --- OUTPUT FRAME ---
        self.output_frame = ctk.CTkFrame(self)
        self.output_frame.grid(row=1, column=0, padx=20, pady=(0, 20), sticky="nsew")
        self.output_frame.grid_rowconfigure(0, weight=1)
        self.output_frame.grid_columnconfigure(0, weight=1)
        
        self.result_text = ctk.CTkTextbox(self.output_frame, state="disabled", wrap="none")
        self.result_text.grid(row=0, column=0, padx=10, pady=10, sticky="nsew")
        
        # Status Bar
        self.status_label = ctk.CTkLabel(self, text="Ready", anchor="w")
        self.status_label.grid(row=2, column=0, padx=20, pady=(0, 10), sticky="ew")

    def browse_dir(self):
        d = filedialog.askdirectory(initialdir=self.out_dir_entry.get())
        if d:
            self.out_dir_entry.delete(0, tk.END)
            self.out_dir_entry.insert(0, d)

    def run_search(self):
        query = self.journal_entry.get().strip()
        if not query:
            return
            
        self.search_btn.configure(state="disabled")
        self.result_list.populate([]) # Clear
        self.update_status(f"Searching for '{query}'...")
        
        t = threading.Thread(target=self.search_logic, args=(query,))
        t.daemon = True
        t.start()

    def search_logic(self, query):
        global get_journal_shortname
        backend = None
        try:
            backend = get_journal_shortname()
            backend.start_session()
            results = backend.search_journal(query)
            
            def _update_ui():
                self.result_list.populate(results)
                self.search_btn.configure(state="normal")
                if not results:
                     self.update_status("No results found.")
                else:
                     self.update_status(f"Found {len(results)} results. Select one.")
                     
            self.after(0, _update_ui)
            
        except Exception as e:
            err_msg = str(e)
            def _err():
                self.update_status(f"Search error: {err_msg}")
                self.search_btn.configure(state="normal")
            self.after(0, _err)
        finally:
             if backend:
                 backend.close()

    def on_list_select(self, val):
        self.journal_entry.delete(0, tk.END)
        self.journal_entry.insert(0, val)

    def start_process(self):
        journal = self.journal_entry.get().strip()
        year_str = self.year_entry.get().strip()
        out_dir = self.out_dir_entry.get().strip()
        
        if not journal:
            return

        if not out_dir:
             return
            
        try:
            start_year = int(year_str)
        except ValueError:
            return

        self.run_btn.configure(state="disabled")
        self.result_text.configure(state="normal")
        self.result_text.delete("1.0", tk.END)
        self.result_text.configure(state="disabled")
        
        t = threading.Thread(target=self.process_logic, args=(journal, start_year, out_dir))
        t.daemon = True
        t.start()
        
    def process_logic(self, journal_input, start_year, out_dir):
        global get_journal_shortname, get_jcr_data, save_jcr_data_csv, calculate_category_averages
        
        try:
            if not os.path.exists(out_dir):
                os.makedirs(out_dir, exist_ok=True)

            # 1. Resolve Name
            self.update_status("Resolving journal name...")
            backend = None
            try:
                backend = get_journal_shortname() 
                backend.start_session()
                results = backend.search_journal(journal_input)
                if not results:
                     raise Exception("No suggestions found.")
                     
                target_journal = None
                for res in results:
                    if res.lower().strip() == journal_input.lower().strip():
                        target_journal = res
                        break
                
                if not target_journal:
                     target_journal = results[0]
                     self.log(f"No exact match. Using: '{target_journal}'")
                
                short_name = backend.select_and_resolve(target_journal)
                self.log(f"Resolved '{journal_input}' -> '{short_name}'")
                
            except Exception as e:
                self.log(f"Could not resolve shortname (using input): {e}")
                short_name = journal_input
            finally:
                if backend:
                    backend.close()
                
            # 2. Scrape Data
            self.update_status(f"Scraping JCR data for '{short_name}'...")
            data = get_jcr_data(short_name)
            
            if not data:
                self.update_status("Error: No data found.")
                self.enable_btn()
                return
                
            # 3. Save Scraped CSV
            csv_filename = os.path.join(out_dir, f"{short_name}_jcr_data.csv")
            save_jcr_data_csv(data, csv_filename)
            self.log(f"Saved raw data to {csv_filename}")
            
            # 4. Analyze
            self.update_status("Analyzing data...")
            averages = calculate_category_averages(csv_filename, start_year)
            
            # 5. Output Table (with stats)
            year_stats = self.extract_year_stats(data, start_year)
            self.display_results(averages, short_name, start_year, year_stats)
            
            # 6. Save Analysis CSV
            out_filename = os.path.join(out_dir, f"{short_name}_averages_{start_year}.csv")
            self.save_analysis_csv(averages, out_filename)
            self.log(f"Saved averages to {out_filename}")
            
            self.update_status("Done.")
            
        except Exception as e:
            self.update_status(f"Error: {e}")
            print(e)
        finally:
            self.enable_btn()

    def result_to_table_str(self, results):
        lines = []
        header = f"{'Metric':<10} | {'Category':<40} | {'5-Yr Avg Percentile':<20}"
        lines.append(header)
        lines.append("-" * len(header))
        for metric, cats in results.items():
            for cat, val in cats.items():
                lines.append(f"{metric:<10} | {cat:<40} | {val:<20}")
        return "\n".join(lines)

    def extract_year_stats(self, data, target_year):
        """Extracts JIF, Rank, and Quartile for the specific year."""
        stats = {
            "jif": data.get("metrics", {}).get("jif", "N/A"),
            "jif_year": data.get("metrics", {}).get("year", "N/A"),
            "categories": []
        }
        
        # Look for rankings in that year
        for cat, rows in data.get("rankings", {}).items():
            for row in rows:
                if row.get("year") == target_year:
                    stats["categories"].append({
                        "name": cat,
                        "rank": row.get("rank", "N/A"),
                        "quartile": row.get("quartile", "N/A")
                    })
        return stats

    def display_results(self, results, journal, year, stats=None):
        table_str = self.result_to_table_str(results)
        
        stats_str = ""
        if stats:
            stats_str += f"Latest JIF ({stats['jif_year']}): {stats['jif']}\n"
            stats_str += f"\nStats for {year}:\n"
            if stats["categories"]:
                for cat in stats["categories"]:
                    stats_str += f"  - {cat['name']}:\n"
                    stats_str += f"    Rank: {cat['rank']}\n"
                    stats_str += f"    Quartile: {cat['quartile']}\n"
            else:
                 stats_str += "  (No specific ranking data found for this year)\n"
            stats_str += "\n" + "="*40 + "\n\n"

        def update_ui():
            self.result_text.configure(state="normal")
            self.result_text.insert(tk.END, f"Analysis for {journal} (Start Year: {year})\n\n")
            if stats_str:
                self.result_text.insert(tk.END, stats_str)
            self.result_text.insert(tk.END, table_str)
            self.result_text.configure(state="disabled")
        self.after(0, update_ui)

    def save_analysis_csv(self, results, filename):
        with open(filename, 'w', newline='', encoding='utf-8') as f:
            writer = csv.writer(f)
            writer.writerow(["Metric", "Category", "5-Year Average Percentile"])
            for metric, cats in results.items():
                for cat, val in cats.items():
                    writer.writerow([metric, cat, val])

    def update_status(self, msg):
        self.after(0, lambda: self.status_label.configure(text=msg))
        
    def log(self, msg):
        def _log():
            self.result_text.configure(state="normal")
            self.result_text.insert(tk.END, f"> {msg}\n")
            self.result_text.see(tk.END)
            self.result_text.configure(state="disabled")
        self.after(0, _log)

    def enable_btn(self):
        self.after(0, lambda: self.run_btn.configure(state="normal"))

def load_modules(app_instance, loading_label, loading_win):
    global get_journal_shortname, get_jcr_data, save_jcr_data_csv, calculate_category_averages
    
    try:
        from jcr_search_cli import JCRBackend
        from extract_jcr_data import get_jcr_data as _get_data, save_csv as _save_csv
        from jcr_analysis import calculate_category_averages as _calc_avg
        
        get_journal_shortname = JCRBackend
        get_jcr_data = _get_data
        save_jcr_data_csv = _save_csv
        calculate_category_averages = _calc_avg
        
        if log_file:
            with open(log_file, "a") as f: f.write("Lazy imports successful.\n")
            
    except Exception as e:
        if log_file:
            with open(log_file, "a") as f: f.write(f"Lazy import failed: {e}\n")
        # messagebox replacement? or just print
        print(f"Error loading modules: {e}")
        app_instance.destroy()
        return

    # Destroy loading window and show main app
    loading_win.destroy()
    app_instance.deiconify()

if __name__ == "__main__":
    import multiprocessing
    multiprocessing.freeze_support()
    
    try:
        if log_file:
            with open(log_file, "a") as f: f.write("Initializing App...\n")
            
        app = JCRApp()
        app.withdraw()
        
        # Splash Screen (Now just a small separate window or Toplevel, but simpler to use Standard Tk for splash to avoid theming issues before load)
        splash = tk.Toplevel()
        splash.title("Loading...")
        w, h = 300, 100
        sw = app.winfo_screenwidth()
        sh = app.winfo_screenheight()
        x = (sw - w) // 2
        y = (sh - h) // 2
        splash.geometry(f"{w}x{h}+{x}+{y}")
        
        lbl = tk.Label(splash, text="Initializing JCR Analyzer...\nPlease Wait...", font=("Arial", 12))
        lbl.pack(expand=True, fill="both", padx=20, pady=20)
        splash.update()
        
        app.after(100, lambda: load_modules(app, lbl, splash))
        app.mainloop()
        
    except Exception as e:
        if log_file:
            with open(log_file, "a") as f: f.write(f"Crash in Main: {e}\n")
        raise e
