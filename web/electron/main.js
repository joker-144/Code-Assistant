const { app, BrowserWindow, ipcMain } = require('electron');
const path = require('path');
const { spawn } = require('child_process');

let mainWindow = null;
let apiProcess = null;

const API_PORT = 8000;
const API_URL = `http://127.0.0.1:${API_PORT}`;

function findPythonCommand() {
  const candidates = ['python', 'python3', 'py'];
  const { execSync } = require('child_process');
  for (const cmd of candidates) {
    try { execSync(`where ${cmd}`, { stdio: 'ignore' }); return cmd; } catch {}
  }
  return 'python';
}

function startApiProcess() {
  const isDev = !app.isPackaged;
  let cwd;
  if (isDev) {
    cwd = path.join(__dirname, '..', '..');
    apiProcess = spawn(findPythonCommand(), ['-m', 'dev_agent', 'serve'], {
      cwd, stdio: ['pipe', 'pipe', 'pipe'], shell: true,
      env: { ...process.env, PYTHONUNBUFFERED: '1' },
    });
  } else {
    cwd = path.dirname(app.getPath('exe'));
    apiProcess = spawn(path.join(cwd, 'dev-agent.exe'), ['serve'], {
      cwd, stdio: ['pipe', 'pipe', 'pipe'], shell: true,
      env: { ...process.env, PYTHONUNBUFFERED: '1' },
    });
  }
  apiProcess.stdout.on('data', (d) => console.log(`[API] ${d.toString().trim()}`));
  apiProcess.stderr.on('data', (d) => console.error(`[API] ${d.toString().trim()}`));
  apiProcess.on('close', (code) => console.log(`[API] exited: ${code}`));
}

function waitForApiReady(retries = 40, delay = 500) {
  return new Promise((resolve, reject) => {
    const http = require('http');
    let attempts = 0;
    function check() {
      attempts++;
      const req = http.get(`${API_URL}/health`, (res) => {
        if (res.statusCode === 200) resolve();
        else if (attempts < retries) setTimeout(check, delay);
        else reject(new Error('API timeout'));
      });
      req.on('error', () => {
        if (attempts < retries) setTimeout(check, delay);
        else reject(new Error('API timeout'));
      });
      req.setTimeout(2000, () => {
        req.destroy();
        if (attempts < retries) setTimeout(check, delay);
        else reject(new Error('API timeout'));
      });
    }
    check();
  });
}

function createWindow() {
  mainWindow = new BrowserWindow({
    width: 1200, height: 800, minWidth: 900, minHeight: 600,
    frame: false,
    titleBarStyle: 'hidden',
    title: 'DevAgent',
    webPreferences: {
      preload: path.join(__dirname, 'preload.js'),
      contextIsolation: true, nodeIntegration: false,
    },
    icon: path.join(__dirname, '..', 'public', 'icon.png'),
    show: false,
    backgroundColor: '#0d1117',
  });

  mainWindow.loadURL(API_URL);
  mainWindow.once('ready-to-show', () => mainWindow.show());

  mainWindow.on('maximize', () => mainWindow.webContents.send('window:maximize-change', true));
  mainWindow.on('unmaximize', () => mainWindow.webContents.send('window:maximize-change', false));
  mainWindow.on('closed', () => { mainWindow = null; });
}

// ── Window controls ──
ipcMain.handle('window:minimize', () => mainWindow?.minimize());
ipcMain.handle('window:maximize', () => {
  if (mainWindow?.isMaximized()) mainWindow.unmaximize();
  else mainWindow?.maximize();
});
ipcMain.handle('window:close', () => mainWindow?.close());
ipcMain.handle('window:is-maximized', () => mainWindow?.isMaximized() ?? false);

// ── Version ──
ipcMain.handle('version:check', async () => {
  try {
    const http = require('http');
    return new Promise((resolve) => {
      http.get(`${API_URL}/api/version/check`, (res) => {
        let data = '';
        res.on('data', (c) => data += c);
        res.on('end', () => {
          try { resolve({ success: true, ...JSON.parse(data) }); }
          catch { resolve({ success: false, error: 'Parse error' }); }
        });
      }).on('error', () => resolve({ success: false, error: 'API unreachable' }));
    });
  } catch (e) { return { success: false, error: e.message }; }
});

ipcMain.handle('version:update', async () => {
  try {
    const http = require('http');
    return new Promise((resolve) => {
      const req = http.request(`${API_URL}/api/version/update`, { method: 'POST' },
        (res) => resolve({ success: true, status: res.statusCode }));
      req.on('error', () => resolve({ success: false, error: 'Update fail' }));
      req.end();
    });
  } catch (e) { return { success: false, error: e.message }; }
});

ipcMain.handle('version:current', () => app.getVersion());
ipcMain.handle('is-electron', () => true);

// ── Lifecycle ──
app.whenReady().then(async () => {
  startApiProcess();
  createWindow();
  try { await waitForApiReady(); } catch (e) { console.error('API startup failed:', e.message); }
  mainWindow?.show();
  app.on('activate', () => { if (BrowserWindow.getAllWindows().length === 0) createWindow(); });
});

function killApi() {
  if (apiProcess) {
    apiProcess.kill('SIGTERM');
    setTimeout(() => { if (apiProcess && !apiProcess.killed) apiProcess.kill('SIGKILL'); }, 3000);
  }
}
app.on('window-all-closed', () => { killApi(); app.quit(); });
app.on('before-quit', () => killApi());
