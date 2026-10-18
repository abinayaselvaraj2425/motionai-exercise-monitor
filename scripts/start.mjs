import { spawn } from 'node:child_process';
import { fileURLToPath } from 'node:url';
import path from 'node:path';
import fs from 'node:fs';
const root = path.resolve(path.dirname(fileURLToPath(import.meta.url)), '..');
const venv = path.join(root, '.venv', process.platform === 'win32' ? 'Scripts/python.exe' : 'bin/python');
const command = process.env.MOTIONAI_PYTHON || (fs.existsSync(venv) ? venv : process.platform === 'win32' ? 'python' : 'python3');
const child = spawn(command, ['-m', 'backend.launch', ...process.argv.slice(2)], {
  cwd: root, env: { ...process.env, PYTHONUNBUFFERED: '1' }, stdio: 'inherit', windowsHide: true,
});
child.on('error', error => {
  console.error('Could not start Python. Run INSTALL.bat, or set MOTIONAI_PYTHON to your Python executable.\n' + error.message);
  process.exitCode = 1;
});
child.on('exit', (code, signal) => { process.exitCode = code ?? (signal ? 1 : 0); });
process.on('SIGINT', () => child.kill('SIGINT'));
process.on('SIGTERM', () => child.kill('SIGTERM'));
