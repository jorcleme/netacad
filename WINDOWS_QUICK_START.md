# Quick Start Guide for Windows Users

## 🚀 Super Simple Setup (for non-tech users)

### First Time Setup

1. **Download the project**
   - [GitHub Repository](https://github.com/jorcleme/netacad)
   - `git clone https://github.com/jorcleme/netacad.git`
2. **Find the project folder**
   - `C:\Users\<YourUsername>\projects\netacad` (or wherever you cloned it)
   - Make sure you have the `start.ps1` file in this folder
3. **Open a terminal in the project folder:**
   - **Method 1:** Hold `Shift` and right-click in the project folder, select "Open PowerShell window here"
   - **Method 2:** Press `Windows + R`, type `powershell`, press Enter, then navigate: `cd C:\Users\<YourUsername>\projects\netacad`
   - **Method 3:** In File Explorer, click the address bar, type `powershell`, and press Enter
4. **Run the startup script:**

   ```powershell
   .\start.ps1
   ```

5. **The script will automatically:**
   - Check if Python is installed (and guide you to install it if not)
   - Create a virtual environment for the project
   - Install all required dependencies
   - Check for your NetAcad credentials
6. **When prompted, enter your NetAcad credentials:**
   - Your instructor email address
   - Your NetAcad password (will be hidden as you type)
   - The script will securely save these for future use
7. **Wait** - the application will then run automatically

### Every Time After That

1. **Open a terminal in the project folder** (same methods as above)
2. **Run the startup script:**

   ```powershell
   .\start.ps1
   ```

3. **The script will:**
   - Verify your setup is still working
   - Use your saved credentials automatically
   - Run the course export
4. **Wait** for it to finish (don't close the terminal window!)
5. **Check the `data` folder** for your files

## 📁 Where to Find Your Files

After the application runs, you'll find your exported gradebook data in:

- **`data/csv/`** folder - Files for uploading to platforms
- **`data/markdown/`** folder - Files for AI processing or reading

## ❓ If Something Goes Wrong

### "Python not found" error

1. Install Python from <https://python.org>
2. **IMPORTANT:** Check the box that says "Add Python to PATH"
3. Restart your computer
4. Try again

### "Permission denied" error

1. Open PowerShell as Administrator:
   - Press `Windows + X` and select "Windows PowerShell (Admin)"
   - Navigate to your project folder: `cd C:\Users\<YourUsername>\projects\netacad`
   - Run: `.\start.ps1`

### PowerShell execution policy error

1. Open PowerShell as Administrator
2. Run: `Set-ExecutionPolicy RemoteSigned -Scope CurrentUser`
3. Type "Y" and press Enter
4. Navigate back to your project folder and try running the script again:

   ```powershell
   cd C:\Users\<YourUsername>\projects\netacad
   .\start.ps1
   ```

### Credential issues

1. If you need to update your credentials:
   - Delete the `.env.development` file in the project folder
   - Open a terminal and run `.\start.ps1` again - it will prompt for new credentials
2. If you see "using default values" error:
   - The script detected template credentials
   - It will automatically prompt you to enter real ones in the terminal

### Chrome issues

- Make sure Google Chrome is installed and up to date

## 🆘 Need Help?

1. **Check the `logs` folder** - it contains detailed error information
2. **Take a screenshot** of any error messages
3. **Contact your tech support** with the screenshot and log files

## 🎯 Files You Can Use

The application creates several files for you:

| File Type                     | Location         | Use For                      |
| ----------------------------- | ---------------- | ---------------------------- |
| `.csv` files                  | `data/csv/`      | Uploading to platforms       |
| `.md` files                   | `data/markdown/` | AI processing or reading     |
| `courses_export_summary.json` | `data/`          | Summary of what was exported |

---

**Remember:** Always run `.\start.ps1` from a PowerShell terminal in the project folder - this ensures you can interact with prompts and see all output!
