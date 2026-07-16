const {
  app,
  BrowserWindow,
  dialog,
  ipcMain,
} = require('electron');
const path = require('path');
const fs = require('fs');
const { spawn } = require('child_process');

const BACKEND_STARTUP_TIMEOUT = 30000;

let mainWindow = null;
let backendProcess = null;
let backendPort = null;

// ── 统一版本号读取 ──
function readAppVersion() {
  const candidates = [
    path.join(__dirname, '../../VERSION'),
    path.join(__dirname, '../VERSION'),
    path.join(process.resourcesPath || '', 'VERSION'),
  ];
  for (const p of candidates) {
    try {
      if (fs.existsSync(p)) {
        return fs.readFileSync(p, 'utf-8').trim();
      }
    } catch { /* ignore */ }
  }
  return '0.5.10';
}

const APP_VERSION = readAppVersion();
console.log(`[DevAgent] Version: ${APP_VERSION}`);

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
      env: { ...process.env, DEVAGENT_VERSION: APP_VERSION },
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
      preload: path.join(__dirname, 'preload.cjs'),
      contextIsolation: true,
      nodeIntegration: false,
    },
    icon: path.join(__dirname, '../../public/log.ico'),
  });

  mainWindow.loadURL(`http://localhost:${backendPort}`);

  mainWindow.webContents.on('did-fail-load', (event, errorCode, errorDescription, validatedURL) => {
    console.error(`[DevAgent] Page load failed: ${errorDescription} (code: ${errorCode}) URL: ${validatedURL}`);
    mainWindow.webContents.loadURL(`data:text/html,<h2>DevAgent 加载失败</h2><p>${errorDescription}</p><p>后端地址: ${validatedURL}</p><p>请检查后端是否正常运行。</p>`);
  });

  mainWindow.once('ready-to-show', () => {
    mainWindow.show();
  });

  mainWindow.on('maximize', () => {
    mainWindow?.webContents.send('maximize-change', true);
  });
  mainWindow.on('unmaximize', () => {
    mainWindow?.webContents.send('maximize-change', false);
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

ipcMain.handle('check-version', async () => {
  try {
    const http = require('http');
    return await new Promise((resolve, reject) => {
      http.get(`http://localhost:${backendPort}/api/version/check`, (res) => {
        let data = '';
        res.on('data', (chunk) => data += chunk);
        res.on('end', () => {
          try { resolve(JSON.parse(data)); }
          catch { reject(new Error('Invalid response')); }
        });
      }).on('error', reject);
    });
  } catch (e) {
    return { error: e.message };
  }
});

ipcMain.handle('update-download', async () => {
  return new Promise((resolve, reject) => {
    const http = require('http');
    const req = http.request(`http://localhost:${backendPort}/api/version/download`, {
      method: 'POST',
    }, (res) => {
      let buffer = '';
      res.on('data', (chunk) => {
        buffer += chunk.toString();
        // 解析 SSE 流并推送到渲染进程
        const lines = buffer.split('\n');
        buffer = lines.pop() || '';
        for (const line of lines) {
          if (line.startsWith('data: ')) {
            try {
              const msg = JSON.parse(line.slice(6));
              mainWindow?.webContents.send('update-download-progress', msg);
              if (msg.status === 'done') {
                resolve({ success: true, file_path: msg.file_path });
              } else if (msg.status === 'error') {
                resolve({ success: false, error: msg.message });
              }
            } catch { /* ignore parse errors */ }
          }
        }
      });
      res.on('end', () => {
        if (buffer) {
          // 处理剩余缓冲
          const lines = buffer.split('\n');
          for (const line of lines) {
            if (line.startsWith('data: ')) {
              try {
                const msg = JSON.parse(line.slice(6));
                if (msg.status === 'done') {
                  resolve({ success: true, file_path: msg.file_path });
                  return;
                } else if (msg.status === 'error') {
                  resolve({ success: false, error: msg.message });
                  return;
                }
              } catch { /* ignore */ }
            }
          }
        }
        resolve({ success: false, error: '下载未完成' });
      });
    });
    req.on('error', (e) => resolve({ success: false, error: e.message }));
    req.end();
  });
});

ipcMain.handle('update-install', async (_event, filePath) => {
  try {
    const { exec } = require('child_process');
    // 以管理员权限静默安装
    exec(
      `"${filePath}" /VERYSILENT /SUPPRESSMSGBOXES /NORESTART`,
      (error) => {
        if (error) {
          console.error('[DevAgent] Install error:', error);
        }
      }
    );
    // 给安装程序一点启动时间，然后退出应用
    setTimeout(() => {
      app.quit();
    }, 2000);
    return { success: true };
  } catch (e) {
    return { success: false, error: e.message };
  }
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
