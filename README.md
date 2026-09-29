# HTML Table Generator: Paramount Digital

Build tables visually and copy clean HTML: styled with inline CSS, or completely unstyled so the site's own CSS applies. Includes lists, images, emoji and symbols, data bars, and charts built from the table (HTML, PNG or SVG).

## Running it

**One click:** double-click **`Start Table Generator.bat`**. It starts the helper and opens the tool at <http://localhost:5732>. If it's already running, it just opens it again. Keep the (minimised) window open while you work; closing it stops the helper.

**Desktop / taskbar shortcut:** right-click `create-shortcut.ps1` > *Run with PowerShell* once. It adds an "HTML Table Generator" shortcut with the Paramount icon to your Desktop. Right-click that > *Pin to taskbar*.

**Without Python:** open `index.html` directly. Everything works except "Site preset" (which can still analyse pasted page source).

Manual start: `python app.py` (add `--no-browser` to skip opening a tab). The helper uses only Python's standard library, so there's nothing to install. Browsers can't read another site's CSS directly, which is why this small local helper exists. It:

- only listens on this machine (127.0.0.1)
- only accepts requests from the table generator itself
- refuses private or local network addresses, including via redirects
- caps timeouts, file sizes and the number of stylesheets

If the helper isn't running, the Site preset panel can analyse pasted page source instead (Ctrl+U on the site, copy, paste).

Note: work is saved in the browser per address, so a table made at `file://…/index.html` won't appear at `http://localhost:5732` and vice versa.
