import { spawn } from 'node:child_process';
import { setTimeout as sleep } from 'node:timers/promises';
import { createRequire } from 'node:module';

const require = createRequire(import.meta.url);
const electronBinary = require('electron');
const env = { ...process.env, NODE_ENV: 'development' };
const electronEnv = { ...env };

delete electronEnv.ELECTRON_RUN_AS_NODE;

await sleep(3000);
await runNodeModule(require.resolve('typescript/bin/tsc'), ['-p', 'tsconfig.main.json']);
await runExecutable(electronBinary, ['.'], { env: electronEnv, longRunning: true });

function runNodeModule(modulePath, args, options = {}) {
  return new Promise((resolve, reject) => {
    const child = spawn(process.execPath, [modulePath, ...args], {
      cwd: process.cwd(),
      env,
      stdio: 'inherit',
    });

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

      if (options.longRunning) {
        if (signal === 'SIGINT' || signal === 'SIGTERM') {
          process.exit(0);
        }

        process.exit(code ?? 0);
      }

      if (code === 0) {
        resolve();
        return;
      }

      reject(new Error(`Command failed with code ${code ?? 'unknown'}`));
    });
  });
}

function runExecutable(command, args, options = {}) {
  return new Promise((resolve, reject) => {
    const child = spawn(command, args, {
      cwd: process.cwd(),
      env: options.env ?? env,
      stdio: 'inherit',
    });

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

      if (options.longRunning) {
        if (signal === 'SIGINT' || signal === 'SIGTERM') {
          process.exit(0);
        }

        process.exit(code ?? 0);
      }

      if (code === 0) {
        resolve();
        return;
      }

      reject(new Error(`Command failed with code ${code ?? 'unknown'}`));
    });
  });
}
