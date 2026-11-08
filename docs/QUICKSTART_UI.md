# Quick Start - Web & Desktop UI

Get up and running with nanobot's beautiful Claude Desktop-inspired interface in under 2 minutes.

## Choose Your Interface

### 🌐 Web Interface (No Installation)

```bash
# 1. Start the gateway
uv run python -m nanobot gateway

# 2. Open in browser
# http://localhost:18800

# Done! Start chatting
```

**Pros:** No installation, accessible from any browser, works on any OS
**Cons:** Requires gateway to be running

### 💻 Desktop Application (Windows Only)

#### Option A: Installer (Easiest)

1. Download `nanobot-setup-1.0.0.exe` from releases
2. Double-click and follow prompts
3. Launch from Start Menu
4. Done!

#### Option B: Build from Source

```bash
# 1. Install Node.js (if needed)
# https://nodejs.org/

# 2. Build
cd desktop
npm install
npm run build:win

# 3. Installers in desktop/dist/
# Double-click to install

# 4. Start gateway
uv run python -m nanobot gateway

# 5. Launch app from Start Menu
```

#### Option C: Run During Development

```bash
# 1. Start gateway
uv run python -m nanobot gateway

# 2. Start app (in another terminal)
cd desktop
npm install
npm start

# Press F12 for DevTools
```

## Features

### Chat History
- **View previous chats:** Click any chat in left sidebar
- **Create new chat:** Click `+` button
- **Switch chats:** Click to load
- **Clear history:** Click `🔄 Clear History` (confirmation required)

### Writing Messages
- **Send:** Press Enter (or click Send arrow)
- **New line:** Shift+Enter
- **Formatting:** Full markdown support
  - `**bold**` → **bold**
  - `` `code` `` → `code`
  - `# Heading` → Heading
  - \[link\](url) → link

### Advanced
- **Sidebar toggle:** Mobile only - tap button
- **DevTools:** Press F12 (desktop dev mode)
- **Backend status:** Green dot = connected, red = disconnected
- **Auto-reconnect:** Happens automatically if disconnected

## Common Issues

### App won't connect

```bash
# Verify gateway is running
uv run python -m nanobot gateway

# Check port is available
netstat -ano | findstr :18790

# Check firewall isn't blocking port
```

### Messages not saving

- Clear your browser cache (web)
- Restart app (desktop)
- Check localStorage isn't disabled

### Desktop app installer fails

```bash
# Clean rebuild
cd desktop
rm -r node_modules package-lock.json
npm install
npm run build:win
```

## Tips & Tricks

### Keyboard Shortcuts (Web & Desktop)
- **Enter** - Send message
- **Shift+Enter** - New line
- **F12** - DevTools (dev mode only)

### Mobile Web
- Sidebar collapses to a button
- Touch-friendly buttons
- Responsive design works great on phone

### Performance
- Markdown rendering is fast
- Code highlighting works for most languages
- Works smoothly even with long conversations

## Next: Customization

### Change Colors

Edit `nanobot/channels/web_static/index.html`, find `:root` and modify:

```css
:root {
  --accent: #d97706;     /* Change button/link color */
  --user-bg: #10a37f;    /* Change user message color */
  --text-primary: #ececf1; /* Change text color */
}
```

Then refresh browser.

### Change Sidebar Width

Edit in CSS section:

```css
#sidebar { width: 260px; } /* Change this number */
```

### Build Desktop with Custom Colors

```bash
cd desktop
npm run build:win
# New installer includes your color changes
```

## Documentation

For more details, see:

- **Setup Guide:** `docs/20260213_desktop_app_setup.md`
- **UI Features:** `docs/20260213_ui_features.md`
- **Development:** `docs/20260213_development_guide.md`
- **Implementation:** `docs/20260213_implementation_summary.md`

## Support

1. Check this guide first
2. Read the relevant doc above
3. Check DevTools console for errors (F12)
4. Review GitHub issues

---

**That's it!** Enjoy your beautiful new nanobot interface! 🚀
