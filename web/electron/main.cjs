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
    const { spawn } = require('child_process');
    const fs = require('fs');
    const os = require('os');
    const path = require('path');

    // 验证文件存在
    if (!fs.existsSync(filePath)) {
      return { success: false, error: `安装包不存在: ${filePath}` };
    }

    console.log(`[DevAgent] Starting installer: ${filePath}`);

    // 1. 先杀死后端进程，释放文件锁（安装程序需要替换 dev-agent.exe）
    killBackend();

    // 2. 等待后端进程完全退出
    await new Promise(resolve => setTimeout(resolve, 2500));

    // 3. 写临时 PowerShell 脚本，负责：等待 Electron 退出 → 静默安装 → 启动新版本
    const escapedPath = filePath.replace(/'/g, "''");
    const ps1Script = `# DevAgent 更新脚本 — 由 Electron 自动生成
$ErrorActionPreference = 'Stop'

# 等待 Electron 完全退出
Start-Sleep -Seconds 3

Write-Host "[DevAgent Updater] Starting silent installer: ${escapedPath}"

# 以管理员权限静默安装（-Verb RunAs 触发 UAC 弹窗）
$proc = Start-Process -FilePath '${escapedPath}' -ArgumentList '/VERYSILENT','/SUPPRESSMSGBOXES','/NORESTART' -Verb RunAs -PassThru -Wait
Write-Host "[DevAgent Updater] Installer exited with code: $($proc.ExitCode)"

# 安装完成后启动新版本 — 优先从注册表读取安装路径
$appId = '{B8F3A1D2-6E5C-4A9B-8D7F-1C3E5A7B9D0F}'
$regPaths = @(
    "HKLM:\\SOFTWARE\\Microsoft\\Windows\\CurrentVersion\\Uninstall\\$appId",
    "HKLM:\\SOFTWARE\\WOW6432Node\\Microsoft\\Windows\\CurrentVersion\\Uninstall\\$appId"
)
$launched = $false
foreach ($regPath in $regPaths) {
    try {
        $p = Get-ItemProperty $regPath -ErrorAction SilentlyContinue
        if ($p) {
            # 优先用 InstallLocation，其次用 DisplayIcon
            $exe = $null
            if ($p.InstallLocation -and (Test-Path $p.InstallLocation)) {
                $exe = Join-Path $p.InstallLocation 'DevAgent.exe'
            }
            if (-not $exe -and $p.DisplayIcon) {
                $exe = $p.DisplayIcon -replace '"','' -replace ',-\\d+$',''
            }
            if ($exe -and (Test-Path $exe)) {
                Write-Host "[DevAgent Updater] Launching: $exe"
                Start-Process $exe
                $launched = $true
                break
            }
        }
    } catch { }
}

# 注册表没找到，尝试常见路径
if (-not $launched) {
    $candidates = @(
        'C:\\Program Files\\DevAgent\\DevAgent.exe',
        'C:\\Program Files (x86)\\DevAgent\\DevAgent.exe',
        'D:\\Software\\DevAgent\\DevAgent.exe'
    )
    foreach ($c in $candidates) {
        if (Test-Path $c) {
            Write-Host "[DevAgent Updater] Launching: $c"
            Start-Process $c
            break
        }
    }
}

# 自清理
Remove-Item $MyInvocation.MyCommand.Path -Force
`;

    const ps1Path = path.join(os.tmpdir(), 'devagent_updater.ps1');
    fs.writeFileSync(ps1Path, ps1Script, 'utf-8');

    // 4. 启动 PowerShell 脚本（独立进程，不随 Electron 退出而终止）
    //    不使用 windowsHide，确保 UAC 弹窗能正常显示
    const child = spawn('powershell.exe', [
      '-NoProfile',
      '-ExecutionPolicy', 'Bypass',
      '-File', ps1Path,
    ], {
      detached: true,
      stdio: 'ignore',
    });

    child.unref();

    console.log('[DevAgent] Updater script launched, quitting app...');

    // 5. 退出 Electron（脚本会等待 3 秒后才启动安装程序，确保 Electron 已退出）
    setTimeout(() => {
      app.quit();
    }, 500);

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
