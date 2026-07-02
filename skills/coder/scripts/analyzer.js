#!/usr/bin/env node
/** 自动分析项目技术栈 */
const fs = require("fs");
const path = require("path");

const PROJECT_ROOT = process.argv[2] || process.cwd();
const TECH_DETECTORS = [
  {
    name: "TypeScript",
    files: ["tsconfig.json"],
    deps: ["typescript"],
  },
  { name: "JavaScript", files: ["package.json"], deps: [] },
  { name: "Python", files: ["requirements.txt", "pyproject.toml", "setup.py"], deps: [] },
  { name: "Go", files: ["go.mod"], deps: [] },
  { name: "Rust", files: ["Cargo.toml"], deps: [] },
  { name: "Java", files: ["pom.xml", "build.gradle"], deps: [] },
];

const FRAMEWORK_DETECTORS = [
  { name: "React", deps: ["react", "react-dom"] },
  { name: "Vue", deps: ["vue"] },
  { name: "Next.js", deps: ["next"] },
  { name: "Nuxt", deps: ["nuxt"] },
  { name: "Django", deps: ["django"] },
  { name: "Flask", deps: ["flask"] },
  { name: "Spring Boot", deps: ["spring-boot-starter"] },
];

function detectLanguages() {
  const languages = [];
  const files = fs.readdirSync(PROJECT_ROOT);

  for (const tech of TECH_DETECTORS) {
    const found = tech.files.some((f) => files.includes(f));
    if (found) languages.push(tech.name);
  }

  return languages.length ? languages : ["Unknown"];
}

function detectFrameworks() {
  const frameworks = [];
  const pkgPath = path.join(PROJECT_ROOT, "package.json");

  if (fs.existsSync(pkgPath)) {
    try {
      const pkg = JSON.parse(fs.readFileSync(pkgPath, "utf-8"));
      const allDeps = { ...(pkg.dependencies || {}), ...(pkg.devDependencies || {}) };

      for (const fw of FRAMEWORK_DETECTORS) {
        if (fw.deps.some((d) => allDeps[d])) {
          frameworks.push(fw.name);
        }
      }
    } catch {}
  }

  return frameworks;
}

function analyzeSourceFiles() {
  const extensions = {};
  const walk = (dir) => {
    const items = fs.readdirSync(dir);
    for (const item of items) {
      const full = path.join(dir, item);
      if (fs.statSync(full).isDirectory() && !item.startsWith(".") && item !== "node_modules") {
        walk(full);
      } else {
        const ext = path.extname(item);
        if (ext) extensions[ext] = (extensions[ext] || 0) + 1;
      }
    }
  };

  try {
    walk(PROJECT_ROOT);
  } catch {}

  return Object.entries(extensions)
    .sort((a, b) => b[1] - a[1])
    .slice(0, 5);
}

// Run analysis
const languages = detectLanguages();
const frameworks = detectFrameworks();
const topExts = analyzeSourceFiles();

console.log("\n=== 项目分析结果 ===\n");
console.log(`语言: ${languages.join(", ")}`);
console.log(`框架: ${frameworks.length ? frameworks.join(", ") : "无检测到框架"}`);
console.log(`\n源码文件分布 (TOP5):`);
topExts.forEach(([ext, count]) => console.log(`  ${ext}: ${count} 个文件`));
console.log(`\n项目根目录: ${PROJECT_ROOT}`);
