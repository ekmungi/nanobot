const { app, BrowserWindow, ipcMain } = require('electron');
const path = require('path');

let mainWindow;
let backendUrl = 'http://localhost:18790'; // Default gateway URL
const isDev = process.argv.includes('--dev');

// Create the browser window
function createWindow() {
  mainWindow = new BrowserWindow({
    width: 1200,
    height: 800,
    minWidth: 400,
    minHeight: 600,
    webPreferences: {
      preload: path.join(__dirname, 'preload.js'),
      contextIsolation: true,
      enableRemoteModule: false,
    },
  });

  // Load the web interface
  mainWindow.loadFile(path.join(__dirname, '../nanobot/channels/web_static/index.html'));

  // Open DevTools in development mode
  if (isDev) {
    mainWindow.webContents.openDevTools();
  }

  mainWindow.on('closed', () => {
    mainWindow = null;
  });
}

// App event listeners
app.on('ready', createWindow);

app.on('window-all-closed', () => {
  if (process.platform !== 'darwin') {
    app.quit();
  }
});

app.on('activate', () => {
  if (mainWindow === null) {
    createWindow();
  }
});

// IPC handlers
ipcMain.handle('get-backend-url', () => {
  return backendUrl;
});

ipcMain.handle('set-backend-url', (event, url) => {
  backendUrl = url;
  return { success: true };
});

ipcMain.handle('check-backend-health', async () => {
  try {
    const controller = new AbortController();
    const timeout = setTimeout(() => controller.abort(), 5000);
    const response = await fetch(`${backendUrl}/health`, { signal: controller.signal });
    clearTimeout(timeout);
    if (response.ok) {
      const data = await response.json();
      return { connected: true, version: data.version || '1.0.0' };
    }
    return { connected: false, error: 'Health check failed' };
  } catch (error) {
    return { connected: false, error: error.message };
  }
});

ipcMain.handle('get-app-version', () => {
  return app.getVersion();
});

// Handle any uncaught exceptions
process.on('uncaughtException', (error) => {
  console.error('Uncaught exception:', error);
});
