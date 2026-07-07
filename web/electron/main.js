const { app, BrowserWindow, ipcMain, dialog } = require('electron');
const path = require('path');
const { spawn } = require('child_process');

let mainWindow = null;
let apiProcess = null;

const API_PORT = 8000;
const API_URL = `http://127.0.0.1:${API_PORT}`;

function findPythonCommand() {
  // Try common Python command names
  const candidates = ['python', 'python3', 'py'];
  const { execSync } = require('child_process');
  for (const cmd of candidates) {
    try {
      execSync(`where ${cmd}`, { stdio: 'ignore' });
      return cmd;
    } catch {}
  }
  return 'python';
}

function startApiProcess() {
  // Determine if running as bundled app or dev mode
  const isDev = !app.isPackaged;

  let devAgentCmd;
  let cwd;

  if (isDev) {
    // Dev mode: run from project root
    cwd = path.join(__dirname, '..', '..');
    devAgentCmd = findPythonCommand();
    apiProcess = spawn(devAgentCmd, ['-m', 'dev_agent', 'serve'], {
      cwd,
      stdio: ['pipe', 'pipe', 'pipe'],
      shell: true,
      env: { ...process.env, PYTHONUNBUFFERED: '1' },
    });
  } else {
    // Bundled mode: dev-agent.exe is in same folder as the Electron app
    cwd = path.dirname(app.getPath('exe'));
    const exePath = path.join(cwd, 'dev-agent.exe');
    apiProcess = spawn(exePath, ['serve'], {
      cwd,
      stdio: ['pipe', 'pipe', 'pipe'],
      shell: true,
      env: { ...process.env, PYTHONUNBUFFERED: '1' },
    });
  }

  apiProcess.stdout.on('data', (data) => {
    console.log(`[API] ${data.toString().trim()}`);
  });

  apiProcess.stderr.on('data', (data) => {
    console.error(`[API] ${data.toString().trim()}`);
  });

  apiProcess.on('close', (code) => {
    console.log(`[API] Process exited with code ${code}`);
  });
}

function waitForApiReady(retries = 30, delay = 500) {
  return new Promise((resolve, reject) => {
    const http = require('http');
    let attempts = 0;

    function check() {
      attempts++;
      const req = http.get(`${API_URL}/health`, (res) => {
        if (res.statusCode === 200) {
          resolve();
        } else if (attempts < retries) {
          setTimeout(check, delay);
        } else {
          reject(new Error('API did not become ready in time'));
        }
      });
      req.on('error', () => {
        if (attempts < retries) {
          setTimeout(check, delay);
        } else {
          reject(new Error('API did not become ready in time'));
        }
      });
      req.setTimeout(2000, () => {
        req.destroy();
        if (attempts < retries) {
          setTimeout(check, delay);
        } else {
          reject(new Error('API did not become ready in time'));
        }
      });
    }
    check();
  });
}

function createWindow() {
  mainWindow = new BrowserWindow({
    width: 1200,
    height: 800,
    minWidth: 900,
    minHeight: 600,
    title: 'DevAgent',
    autoHideMenuBar: true,
    webPreferences: {
      preload: path.join(__dirname, 'preload.js'),
      contextIsolation: true,
      nodeIntegration: false,
    },
    icon: path.join(__dirname, '..', 'public', 'icon.png'),
    show: false,
  });

  mainWindow.loadURL(API_URL);

  mainWindow.once('ready-to-show', () => {
    mainWindow.show();
  });

  mainWindow.on('closed', () => {
    mainWindow = null;
  });
}

// IPC handlers

// Check for updates - communicates with the Python API
ipcMain.handle('version:check', async () => {
  try {
    const http = require('http');
    return new Promise((resolve) => {
      http.get(`${API_URL}/api/version/check`, (res) => {
        let data = '';
        res.on('data', (chunk) => data += chunk);
        res.on('end', () => {
          try {
            resolve({ success: true, ...JSON.parse(data) });
          } catch {
            resolve({ success: false, error: 'Failed to parse version data' });
          }
        });
      }).on('error', () => {
        resolve({ success: false, error: 'API not reachable' });
      });
    });
  } catch (e) {
    return { success: false, error: e.message };
  }
});

// Trigger update
ipcMain.handle('version:update', async () => {
  try {
    const http = require('http');
    return new Promise((resolve) => {
      const req = http.request(`${API_URL}/api/version/update`, {
        method: 'POST',
        headers: { 'Content-Type': 'application/json' },
      }, (res) => {
        resolve({ success: true, status: res.statusCode });
      });
      req.on('error', () => {
        resolve({ success: false, error: 'Update request failed' });
      });
      req.end();
    });
  } catch (e) {
    return { success: false, error: e.message };
  }
});

// Get current version
ipcMain.handle('version:current', () => {
  return app.getVersion();
});

// Check if running in Electron
ipcMain.handle('is-electron', () => {
  return true;
});

// App lifecycle
app.whenReady().then(async () => {
  startApiProcess();
  createWindow();

  // Show window even if API startup fails - let the user see the loading page
  try {
    await waitForApiReady(40, 500);
  } catch (e) {
    console.error('API startup failed:', e.message);
  }

  mainWindow.show();

  app.on('activate', () => {
    if (BrowserWindow.getAllWindows().length === 0) {
      createWindow();
    }
  });
});

app.on('window-all-closed', () => {
  // Kill API process if still running
  if (apiProcess) {
    apiProcess.kill('SIGTERM');
    // Force kill after 3 seconds
    setTimeout(() => {
      if (apiProcess && !apiProcess.killed) {
        apiProcess.kill('SIGKILL');
      }
    }, 3000);
  }
  app.quit();
});

app.on('before-quit', () => {
  if (apiProcess) {
    apiProcess.kill('SIGTERM');
    setTimeout(() => {
      if (apiProcess && !apiProcess.killed) {
        apiProcess.kill('SIGKILL');
      }
    }, 3000);
  }
});
