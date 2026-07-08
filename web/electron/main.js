const {
  app,
  BrowserWindow,
  dialog,
  ipcMain,
} = require('electron');
const path = require('path');
const { spawn } = require('child_process');

const BACKEND_STARTUP_TIMEOUT = 30000;

let mainWindow = null;
let backendProcess = null;
let backendPort = null;

function getBackendPath() {
  if (app.isPackaged) {
    return path.join(process.resourcesPath, 'backend', 'dev-agent.exe');
  }
  return path.join(__dirname, '../../dist/dev-agent.exe');
}

function startBackend() {
  return new Promise((resolve, reject) => {
    const backendPath = getBackendPath();
    console.log(`[DevAgent] Starting backend: ${backendPath}`);

    backendProcess = spawn(backendPath, ['serve', '--port', '0'], {
      stdio: ['ignore', 'pipe', 'pipe'],
      windowsHide: true,
    });

    let firstLine = '';
    const timeout = setTimeout(() => {
      reject(new Error('Backend startup timed out after 30 seconds'));
    }, BACKEND_STARTUP_TIMEOUT);

    backendProcess.stdout.on('data', (data) => {
      const text = data.toString();
      if (!firstLine) {
        const newlineIdx = text.indexOf('\n');
        if (newlineIdx !== -1) {
          firstLine += text.substring(0, newlineIdx);
          clearTimeout(timeout);

          const portMatch = firstLine.match(/port[:\s]*(\d+)/i);
          if (portMatch) {
            backendPort = parseInt(portMatch[1], 10);
          } else {
            const numMatch = firstLine.match(/(\d{4,5})/);
            if (numMatch) {
              backendPort = parseInt(numMatch[1], 10);
            }
          }

          if (backendPort) {
            console.log(`[DevAgent] Backend started on port ${backendPort}`);
            resolve(backendPort);
          } else {
            console.log(`[DevAgent] Backend first line: ${firstLine}`);
            backendPort = parseInt(firstLine.trim(), 10);
            if (isNaN(backendPort)) {
              reject(new Error(`Could not parse port from backend output: ${firstLine}`));
            } else {
              console.log(`[DevAgent] Backend started on port ${backendPort}`);
              resolve(backendPort);
            }
          }
        } else {
          firstLine += text;
          if (firstLine.length > 500) {
            clearTimeout(timeout);
            reject(new Error('Backend output too long without valid port'));
          }
        }
      }
    });

    backendProcess.stderr.on('data', (data) => {
      console.error(`[DevAgent Backend] ${data.toString()}`);
    });

    backendProcess.on('error', (err) => {
      clearTimeout(timeout);
      reject(new Error(`Failed to start backend: ${err.message}`));
    });

    backendProcess.on('exit', (code, signal) => {
      clearTimeout(timeout);
      if (!backendPort) {
        reject(new Error(`Backend exited with code ${code} before reporting port`));
      }
    });
  });
}

function killBackend() {
  if (backendProcess && !backendProcess.killed) {
    console.log('[DevAgent] Stopping backend...');
    try {
      backendProcess.kill('SIGTERM');
    } catch (e) {
      // ignore
    }

    const forceKillTimeout = setTimeout(() => {
      if (backendProcess && !backendProcess.killed) {
        try {
          backendProcess.kill('SIGKILL');
        } catch (e) {
          // ignore
        }
      }
    }, 5000);

    backendProcess.on('exit', () => {
      clearTimeout(forceKillTimeout);
    });
  }
}

function createWindow() {
  mainWindow = new BrowserWindow({
    width: 1280,
    height: 800,
    minWidth: 900,
    minHeight: 600,
    frame: false,
    show: false,
    webPreferences: {
      preload: path.join(__dirname, 'preload.js'),
      contextIsolation: true,
      nodeIntegration: false,
    },
    icon: path.join(__dirname, '../../public/icon.png'),
  });

  mainWindow.loadURL(`http://localhost:${backendPort}`);

  mainWindow.once('ready-to-show', () => {
    mainWindow.show();
  });

  mainWindow.on('closed', () => {
    mainWindow = null;
  });
}

// IPC handlers for frameless window controls
ipcMain.handle('window-minimize', () => {
  if (mainWindow) mainWindow.minimize();
});

ipcMain.handle('window-maximize', () => {
  if (mainWindow) {
    if (mainWindow.isMaximized()) {
      mainWindow.unmaximize();
    } else {
      mainWindow.maximize();
    }
  }
});

ipcMain.handle('window-close', () => {
  if (mainWindow) mainWindow.close();
});

ipcMain.handle('window-is-maximized', () => {
  return mainWindow ? mainWindow.isMaximized() : false;
});

app.whenReady().then(async () => {
  try {
    await startBackend();
    createWindow();
  } catch (err) {
    dialog.showErrorBox(
      'DevAgent Startup Error',
      `Failed to start the backend service:\n\n${err.message}\n\nPlease ensure dev-agent.exe is available and try again.`
    );
    app.quit();
  }
});

app.on('window-all-closed', () => {
  killBackend();
  app.quit();
});

app.on('before-quit', () => {
  killBackend();
});

app.on('activate', () => {
  if (mainWindow === null) {
    createWindow();
  }
});

// Prevent multiple instances
const gotLock = app.requestSingleInstanceLock();
if (!gotLock) {
  app.quit();
} else {
  app.on('second-instance', () => {
    if (mainWindow) {
      if (mainWindow.isMinimized()) mainWindow.restore();
      mainWindow.focus();
    }
  });
}
