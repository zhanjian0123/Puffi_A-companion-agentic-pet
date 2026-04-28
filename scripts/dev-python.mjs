import { spawn } from 'node:child_process';
import path from 'node:path';

const rootDir = process.cwd();
const pythonDir = path.join(rootDir, 'python');
const pythonExecutable =
  process.platform === 'win32'
    ? path.join(rootDir, '.venv', 'Scripts', 'python.exe')
    : path.join(rootDir, '.venv', 'bin', 'python');
const host = process.env.AI_PET_AGENT_HOST || '127.0.0.1';
const port = process.env.AI_PET_AGENT_PORT || '8787';

const child = spawn(
  pythonExecutable,
  ['-m', 'uvicorn', 'main:app', '--host', host, '--port', port, '--log-level', 'debug'],
  {
    cwd: pythonDir,
    env: process.env,
    stdio: 'inherit',
  }
);

const forwardSignal = (signal) => {
  if (!child.killed) {
    child.kill(signal);
  }
};

process.once('SIGINT', forwardSignal);
process.once('SIGTERM', forwardSignal);

child.on('exit', (code, signal) => {
  process.removeListener('SIGINT', forwardSignal);
  process.removeListener('SIGTERM', forwardSignal);

  if (signal === 'SIGINT' || signal === 'SIGTERM') {
    process.exit(0);
  }

  process.exit(code ?? 0);
});
