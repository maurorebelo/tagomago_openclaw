#!/usr/bin/env node
/**
 * Ensures agents.defaults.workspace is "/data" and optionally adds
 * skills.load.extraDirs with "/data/skills". Run on the VPS inside the
 * OpenClaw container (cwd = /data):
 *   node /data/scripts/ensure-workspace-config.js
 * Script lives in the repo (GitHub canonical); VPS has it after git pull.
 */

const fs = require('fs');
const path = require('path');

const configPath = process.env.OPENCLAW_CONFIG || path.join(process.cwd(), '.openclaw', 'openclaw.json');
const workspaceExpected = '/data';

let raw;
try {
  raw = fs.readFileSync(configPath, 'utf8');
} catch (e) {
  console.error('Cannot read config at', configPath, e.message);
  process.exit(1);
}

let config;
try {
  config = JSON.parse(raw);
} catch (e) {
  console.error('Invalid JSON in config', e.message);
  process.exit(1);
}

if (!config.agents) config.agents = {};
if (!config.agents.defaults) config.agents.defaults = {};
const changed = [];

if (config.agents.defaults.workspace !== workspaceExpected) {
  config.agents.defaults.workspace = workspaceExpected;
  changed.push('agents.defaults.workspace -> "/data"');
}

if (!config.skills) config.skills = {};
if (!config.skills.load) config.skills.load = {};
let extraDirs = config.skills.load.extraDirs;
if (!Array.isArray(extraDirs)) extraDirs = [];
const skillsDir = '/data/skills';
if (!extraDirs.includes(skillsDir)) {
  extraDirs.push(skillsDir);
  config.skills.load.extraDirs = extraDirs;
  changed.push('skills.load.extraDirs includes "/data/skills"');
}

if (changed.length === 0) {
  console.log('Config already has workspace "/data" and extraDirs; no changes.');
  process.exit(0);
}

fs.writeFileSync(configPath, JSON.stringify(config, null, 2), 'utf8');
console.log('Updated', configPath, ':', changed.join('; '));
