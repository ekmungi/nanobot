# nanobot Desktop Application

A native Windows desktop application for nanobot built with Electron.

## Features

- Native Windows application with Claude Desktop-inspired UI
- Connects to the nanobot gateway server
- Chat history management with local storage
- Beautiful dark theme matching Claude Desktop aesthetics
- Sidebar navigation for managing chats
- Markdown support for responses

## Installation

### From Binary

Download the latest installer from releases and run it. This will install nanobot to your system.

### From Source

#### Prerequisites

- Node.js 18+ and npm
- The nanobot gateway running locally on `http://localhost:18790`

#### Development Setup

```bash
cd desktop
npm install
npm start
```

#### Build for Distribution

```bash
cd desktop
npm install
npm run build:win
```

This creates an installer in `dist/` directory.

## Configuration

The app expects the nanobot gateway to be running on `http://localhost:18790`. You can modify this in `main.js` if needed.

## Architecture

- **main.js** - Electron main process, window management, IPC handlers
- **preload.js** - Secure context bridge between renderer and main process
- **index.html** - Web UI (located in `../nanobot/channels/web_static/`)

## Development

### Run in Development Mode

```bash
npm run dev
```

This opens DevTools for debugging.

### Debugging

DevTools can be opened with F12 or via the dev mode flag. Check the console for any errors.

## Building

### Create Windows Installer

```bash
npm run build:win
```

Creates:
- NSIS installer (.exe)
- Portable executable (.exe)

### Custom Build

For other platforms or configurations, edit the `build` section in `package.json`.

## Troubleshooting

### App won't connect to backend

1. Ensure nanobot gateway is running: `uv run python -m nanobot gateway`
2. Check it's listening on `http://localhost:18790`
3. Check firewall settings

### White screen on startup

- Check DevTools console for errors (F12)
- Verify `index.html` path in `main.js`

### Building fails

- Delete `node_modules` and `package-lock.json`
- Run `npm install` again
- Ensure Node.js is up to date

## Distribution

The app can be distributed via:

1. **Installer (NSIS)** - Users can install to Program Files
2. **Portable** - Single executable, no installation needed
3. **Microsoft Store** - For wider distribution (requires additional setup)

## Future Enhancements

- [ ] Auto-update functionality
- [ ] Tray icon support
- [ ] Keyboard shortcuts (Ctrl+/, Cmd+K, etc.)
- [ ] Settings dialog for backend URL configuration
- [ ] Export chat history
- [ ] Dark/light theme toggle
