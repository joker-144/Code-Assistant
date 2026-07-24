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
const DEFAULT_PORT = 19476;

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

function _parseBackendPort(firstLine) {
  // 尝试多种格式解析端口号
  const portMatch = firstLine.match(/port[:\s]*(\d+)/i);
  if (portMatch) return parseInt(portMatch[1], 10);
  const numMatch = firstLine.match(/(\d{4,5})/);
  if (numMatch) return parseInt(numMatch[1], 10);
  const parsed = parseInt(firstLine.trim(), 10);
  return isNaN(parsed) ? null : parsed;
}

function _launchBackend(port) {
  const backendPath = getBackendPath();
  const portArg = String(port);
  console.log(`[DevAgent] Starting backend: ${backendPath} --port ${portArg}`);
  backendProcess = spawn(backendPath, ['serve', '--port', portArg], {
    stdio: ['ignore', 'pipe', 'pipe'],
    windowsHide: true,
    env: { ...process.env, DEVAGENT_VERSION: APP_VERSION },
  });
}

function startBackend() {
  return new Promise((resolve, reject) => {
    let isFirstLaunch = true;
    let attemptPort = DEFAULT_PORT;

    function onPortResolved(port) {
      backendPort = port;
      console.log(`[DevAgent] Backend started on port ${backendPort}`);
      resolve(backendPort);
    }

    function tryLaunch(port) {
      _launchBackend(port);

      let firstLine = '';
      const timeout = setTimeout(() => {
        if (isFirstLaunch) {
          reject(new Error('Backend startup timed out after 30 seconds'));
        } else {
          // 固定端口被占用，自动切为随机端口后仍然超时
          reject(new Error('Backend startup timed out — both fixed port and random port failed'));
        }
      }, BACKEND_STARTUP_TIMEOUT);

      backendProcess.stdout.on('data', (data) => {
        const text = data.toString();
        if (!firstLine) {
          const newlineIdx = text.indexOf('\n');
          if (newlineIdx !== -1) {
            firstLine += text.substring(0, newlineIdx);
            clearTimeout(timeout);

            const parsedPort = _parseBackendPort(firstLine);
            if (parsedPort) {
              return onPortResolved(parsedPort);
            }
            // 端口解析失败：先打印输出，如果是首次尝试，则自动切随机端口重试
            console.log(`[DevAgent] Backend stdout: ${firstLine}`);
            if (isFirstLaunch) {
              console.log('[DevAgent] Port parsing failed, retrying with random port...');
              isFirstLaunch = false;
              killBackend();
              return tryLaunch(0);
            }
            reject(new Error(`Could not parse port from backend output: ${firstLine}`));
          } else {
            firstLine += text;
            if (firstLine.length > 500) {
              clearTimeout(timeout);
              if (isFirstLaunch) {
                console.log('[DevAgent] Backend stdout too long, retrying with random port...');
                isFirstLaunch = false;
                killBackend();
                return tryLaunch(0);
              }
              reject(new Error('Backend output too long without valid port'));
            }
          }
        }
      });

      backendProcess.stderr.on('data', (data) => {
        const errText = data.toString();
        console.error(`[DevAgent Backend] ${errText}`);
        // 检测端口占用错误
        if (isFirstLaunch && (errText.includes('Address already in use') || errText.includes('address in use') || errText.includes('EADDRINUSE'))) {
          clearTimeout(timeout);
          console.log('[DevAgent] Fixed port in use, trying random port...');
          isFirstLaunch = false;
          killBackend();
          tryLaunch(0);
        }
      });

      backendProcess.on('error', (err) => {
        clearTimeout(timeout);
        if (isFirstLaunch) {
          isFirstLaunch = false;
          killBackend();
          return tryLaunch(0);
        }
        reject(new Error(`Failed to start backend: ${err.message}`));
      });

      backendProcess.on('exit', (code, signal) => {
        clearTimeout(timeout);
        if (!backendPort) {
          if (isFirstLaunch) {
            isFirstLaunch = false;
            killBackend();
            return tryLaunch(0);
          }
          reject(new Error(`Backend exited with code ${code} before reporting port`));
        }
      });
    }

    tryLaunch(DEFAULT_PORT);
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

  // Windows 上 SIGTERM/SIGKILL 不可靠，用 taskkill /F /T 强制杀死整个进程树
  // 包括 dev-agent.exe 及其可能派生的子进程（如 uvicorn worker）
  try {
    const { execSync } = require('child_process');
    execSync('taskkill /F /IM dev-agent.exe /T', { stdio: 'ignore', windowsHide: true });
    console.log('[DevAgent] All dev-agent.exe processes killed via taskkill');
  } catch (e) {
    // taskkill 退出码 128 = 没有找到进程，属于正常情况
    if (!String(e.message).includes('128')) {
      console.log('[DevAgent] taskkill completed (no remaining processes)');
    }
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
    const { exec, execSync } = require('child_process');
    const fs = require('fs');
    const os = require('os');
    const path = require('path');

    // 验证文件存在
    if (!fs.existsSync(filePath)) {
      return { success: false, error: `安装包不存在: ${filePath}` };
    }

    console.log(`[DevAgent] Starting installer: ${filePath}`);

    // 1. 写临时批处理脚本
    //    关键变化: 使用 Windows RunOnce 注册表机制保证安装程序在 app 退出后仍能执行
    //    RunOnce 由 explorer.exe 处理，完全脱离 Electron 的作业对象（Job Object）
    const escapedPath = filePath.replace(/'/g, "''");
    // 当前运行的可执行文件路径 — 无论装在哪个目录都准确可靠
    const currentExePath = process.execPath;
    const escapedExePath = currentExePath.replace(/'/g, "''");
    const batScript = `@echo off
REM DevAgent 更新脚本 — RunOnce 自动执行（由 Windows Explorer 调度，独立于 Electron 进程树）
title DevAgent 更新程序
echo [DevAgent Updater] 等待应用退出...
ping 127.0.0.1 -n 6 > nul

echo [DevAgent Updater] 正在静默安装...
start /wait "" "${escapedPath}" /VERYSILENT /SUPPRESSMSGBOXES /NORESTART
echo [DevAgent Updater] 安装完成（退出码: %ERRORLEVEL%）

REM 启动新版本（路径由 Electron 在生成脚本时直接传入，通用所有安装目录）
start "" "${escapedExePath}"

REM 清理 RunOnce 注册表项（防止系统重启后重复执行）
reg delete "HKCU\\Software\\Microsoft\\Windows\\CurrentVersion\\RunOnce" /v "DevAgentUpdate" /f > nul 2>&1

REM 自清理
del "%~f0" > nul 2>&1
`;

    const batPath = path.join(os.tmpdir(), 'devagent_updater.bat');
    fs.writeFileSync(batPath, batScript, 'utf-8');

    // 2. 注册 RunOnce（▸ 主保障 ◂）
    //    RunOnce 由 Windows Explorer（explorer.exe）在用户会话中处理，
    //    完全独立于 Electron 的作业对象。即使 app.quit() 立即回收 Job Object，
    //    RunOnce 仍会在应用退出后正常执行。
    try {
      execSync(
        `reg add "HKCU\\Software\\Microsoft\\Windows\\CurrentVersion\\RunOnce" /v "DevAgentUpdate" /t REG_SZ /d "\"${batPath}\"" /f`,
        { stdio: 'ignore', timeout: 5000 }
      );
      console.log('[DevAgent] RunOnce registered for update');
    } catch (regErr) {
      console.warn('[DevAgent] Failed to register RunOnce:', regErr.message);
    }

    // 3. 尝试直接启动（快速路径 — 可能在 app.quit 前有机会创建新窗口）
    try {
      const child = exec(
        `start "DevAgent 更新程序" /MIN "${batPath}"`,
        { shell: 'cmd.exe', windowsHide: false }
      );
      child.unref();
    } catch (e) {
      console.warn('[DevAgent] Direct launch failed:', e.message);
    }

    // 4. 先杀死后端进程，释放文件锁
    killBackend();
    await new Promise(resolve => setTimeout(resolve, 2000));

    console.log('[DevAgent] Quitting app, RunOnce will complete the update...');

    // 5. 退出 Electron
    //    RunOnce 注册表项确保 bat 脚本在应用退出后仍会被执行
    app.quit();

    return { success: true };
  } catch (e) {
    console.error('[DevAgent] Install error:', e);
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
