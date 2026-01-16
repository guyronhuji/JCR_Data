# Building JCR GUI for Windows

Since PyInstaller builds are platform-specific, you must run the build process on a Windows machine to create a `.exe` file.

## Prerequisites

1.  **Python 3.10+**: Ensure Python is installing and added to your `PATH`.
2.  **Git**: To clone the repository (or just copy the files).
3.  **Browsers**: Ensure you have Chrome/Chromium installed, or run `playwright install chromium` after setting up dependencies.

## Setup Steps

1.  **Open Command Prompt or PowerShell**.
2.  **Navigate to the project folder**.
3.  **Create a Virtual Environment** (Recommended):
    ```powershell
    python -m venv venv
    .\venv\Scripts\activate
    ```
4.  **Install Dependencies**:
    ```powershell
    pip install playwright customtkinter
    playwright install chromium
    pip install pyinstaller
    ```
    *(Note: `customtkinter` is optional if you reverted to standard `tkinter`, but `playwright` is required.)*

## Build Command

Run the following command in your terminal:

```powershell
pyinstaller --noconfirm --onefile --windowed --name "JCR_Analyzer" --hidden-import "tkinter" --hidden-import "playwright" "jcr_gui.py"
```

## Post-Build

1.  The executable will be in the `dist/` folder named `JCR_Analyzer.exe`.
2.  **Important**: On the first run, the app will try to find your system installation of Chromium (usually in `%LOCALAPPDATA%\ms-playwright\`).
    - If it fails to find the browser, ensure you have run `playwright install chromium` on that machine.

## Troubleshooting

-   **"Browser not found"**: The app logs debug info to `%USERPROFILE%\jcr_debug.log`. Check this file to see where it looked for the browser.
-   **Console window appearing**: We used `--windowed`, but if a console still appears, ensure you didn't run with `--debug`.
