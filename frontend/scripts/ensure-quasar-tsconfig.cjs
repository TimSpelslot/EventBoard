/**
 * Ensures .quasar/tsconfig.json exists so the root tsconfig.json "extends" resolves.
 * Used in CI and when running tests without having run "quasar build" or "quasar dev" first.
 */
const fs = require('fs');
const path = require('path');

const dir = path.join(__dirname, '..', '.quasar');
const file = path.join(dir, 'tsconfig.json');

const config = {
  compilerOptions: {
    target: 'ESNext',
    module: 'ESNext',
    moduleResolution: 'bundler',
    strict: true,
    jsx: 'preserve',
    resolveJsonModule: true,
    isolatedModules: true,
    esModuleInterop: true,
    lib: ['ESNext', 'DOM'],
    baseUrl: '.',
    types: ['node'],
  },
  include: ['src/**/*', 'tests/**/*'],
  exclude: ['node_modules'],
};

if (!fs.existsSync(dir)) {
  fs.mkdirSync(dir, { recursive: true });
}

if (!fs.existsSync(file)) {
  fs.writeFileSync(file, JSON.stringify(config, null, 2), 'utf8');
  console.log('Created .quasar/tsconfig.json for test run');
}
