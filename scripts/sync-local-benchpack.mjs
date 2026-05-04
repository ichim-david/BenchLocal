#!/usr/bin/env node

import { existsSync } from "node:fs";
import { copyFile, cp, mkdir, readFile, rm } from "node:fs/promises";
import { homedir } from "node:os";
import path from "node:path";
import { spawnSync } from "node:child_process";

const EXCLUDED_TOP_LEVEL_NAMES = new Set([
  ".git",
  ".DS_Store",
  "node_modules",
  "package-lock.json",
  "tsconfig.tsbuildinfo"
]);

function usage() {
  console.log(`Usage:
  node scripts/sync-local-benchpack.mjs <benchpack-dir> [--benchlocal-home <path>] [--no-build] [--dry-run]

Examples:
  npm run sync:benchpack -- ReasonMath-15
  node scripts/sync-local-benchpack.mjs ReasonMath-15 --dry-run
  node scripts/sync-local-benchpack.mjs /path/to/ReasonMath-15 --benchlocal-home ~/.benchlocal
`);
}

function parseArgs(argv) {
  const args = {
    benchpackDir: "",
    benchlocalHome: path.join(homedir(), ".benchlocal"),
    build: true,
    dryRun: false
  };

  for (let index = 0; index < argv.length; index += 1) {
    const arg = argv[index];

    if (arg === "--help" || arg === "-h") {
      usage();
      process.exit(0);
    }

    if (arg === "--benchlocal-home") {
      args.benchlocalHome = expandHome(argv[index + 1] ?? "");
      index += 1;
      continue;
    }

    if (arg === "--no-build") {
      args.build = false;
      continue;
    }

    if (arg === "--dry-run") {
      args.dryRun = true;
      continue;
    }

    if (!args.benchpackDir) {
      args.benchpackDir = arg;
      continue;
    }

    throw new Error(`Unexpected argument: ${arg}`);
  }

  if (!args.benchpackDir) {
    usage();
    throw new Error("Missing benchpack-dir.");
  }

  args.benchpackDir = path.resolve(expandHome(args.benchpackDir));
  return args;
}

function expandHome(value) {
  if (value === "~") {
    return homedir();
  }

  if (value.startsWith("~/")) {
    return path.join(homedir(), value.slice(2));
  }

  return value;
}

async function readJson(filePath) {
  return JSON.parse(await readFile(filePath, "utf8"));
}

async function assertDirectory(dirPath, label) {
  if (!existsSync(dirPath)) {
    throw new Error(`${label} does not exist: ${dirPath}`);
  }
}

function runBuildIfAvailable(sourceDir, packageJson, dryRun) {
  const hasBuildScript = Boolean(packageJson.scripts?.["build:benchlocal"]);

  if (!hasBuildScript) {
    console.log("No build:benchlocal script found; skipping build.");
    return;
  }

  if (dryRun) {
    console.log(`[dry-run] Would run: npm run build:benchlocal --prefix ${sourceDir}`);
    return;
  }

  console.log("Running bench pack build: npm run build:benchlocal");
  const result = spawnSync("npm", ["run", "build:benchlocal"], {
    cwd: sourceDir,
    stdio: "inherit"
  });

  if (result.status !== 0) {
    throw new Error("Bench pack build failed.");
  }
}

async function listTopLevelEntries(sourceDir) {
  const { readdir } = await import("node:fs/promises");
  return (await readdir(sourceDir, { withFileTypes: true }))
    .filter((entry) => !EXCLUDED_TOP_LEVEL_NAMES.has(entry.name))
    .filter((entry) => !entry.name.endsWith(".tsbuildinfo"));
}

async function syncEntry(sourceDir, targetDir, entry, dryRun) {
  const sourcePath = path.join(sourceDir, entry.name);
  const targetPath = path.join(targetDir, entry.name);

  if (dryRun) {
    console.log(`[dry-run] Would replace ${targetPath}`);
    return;
  }

  await rm(targetPath, { recursive: true, force: true });

  if (entry.isDirectory()) {
    await cp(sourcePath, targetPath, {
      recursive: true,
      filter: (candidate) => !candidate.split(path.sep).includes("node_modules")
    });
    return;
  }

  if (entry.isFile()) {
    await copyFile(sourcePath, targetPath);
  }
}

async function main() {
  const args = parseArgs(process.argv.slice(2));
  await assertDirectory(args.benchpackDir, "Bench pack directory");

  const manifestPath = path.join(args.benchpackDir, "benchlocal.pack.json");
  const manifest = await readJson(manifestPath);
  const packageJsonPath = path.join(args.benchpackDir, "package.json");
  const packageJson = existsSync(packageJsonPath) ? await readJson(packageJsonPath) : {};

  if (!manifest.id) {
    throw new Error(`Bench pack manifest is missing id: ${manifestPath}`);
  }

  if (args.build) {
    runBuildIfAvailable(args.benchpackDir, packageJson, args.dryRun);
  }

  const currentPath = path.join(args.benchlocalHome, "benchpacks", manifest.id, "current.json");
  const current = await readJson(currentPath);
  const targetDir = path.join(args.benchlocalHome, "benchpacks", manifest.id, "versions", current.version);

  await assertDirectory(targetDir, "Installed bench pack version");
  await mkdir(targetDir, { recursive: true });

  console.log(`Source: ${args.benchpackDir}`);
  console.log(`Target: ${targetDir}`);
  console.log(`Bench pack: ${manifest.id}`);
  console.log(`Installed version: ${current.version}`);

  const entries = await listTopLevelEntries(args.benchpackDir);

  for (const entry of entries) {
    await syncEntry(args.benchpackDir, targetDir, entry, args.dryRun);
  }

  console.log(args.dryRun ? "Dry run complete." : "Bench pack sync complete. Restart BenchLocal before retesting.");
}

main().catch((error) => {
  console.error(error instanceof Error ? error.message : error);
  process.exit(1);
});
