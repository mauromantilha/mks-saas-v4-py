import { readdirSync, readFileSync, statSync } from "node:fs";
import { join } from "node:path";

const ROOT = new URL("..", import.meta.url).pathname;
const SRC = join(ROOT, "src");

const CONTROL_PATTERN =
  /(matInput|<mat-select\b|matNativeControl|<textarea[^>]*\bmatInput\b|<mat-chip-grid\b|<mat-chip-listbox\b|<mat-date-range-input\b|matDatepicker)/s;

function walk(dir) {
  const entries = readdirSync(dir);
  const files = [];
  for (const entry of entries) {
    const full = join(dir, entry);
    const stats = statSync(full);
    if (stats.isDirectory()) {
      files.push(...walk(full));
      continue;
    }
    if (full.endsWith(".html")) {
      files.push(full);
    }
  }
  return files;
}

function countLine(text, index) {
  return text.slice(0, index).split("\n").length;
}

function checkFile(file) {
  const content = readFileSync(file, "utf-8");
  const regex = /<mat-form-field\b[^>]*>([\s\S]*?)<\/mat-form-field>/g;
  const issues = [];
  for (const match of content.matchAll(regex)) {
    const block = match[1] || "";
    if (!CONTROL_PATTERN.test(block)) {
      issues.push({
        file,
        line: countLine(content, match.index ?? 0),
      });
    }
  }
  return issues;
}

const allHtml = walk(SRC);
const allIssues = allHtml.flatMap(checkFile);

if (allIssues.length === 0) {
  console.log("OK: no suspicious mat-form-field blocks found.");
  process.exit(0);
}

console.error("ERROR: suspicious mat-form-field blocks found:");
for (const issue of allIssues) {
  console.error(`- ${issue.file}:${issue.line}`);
}
process.exit(1);

