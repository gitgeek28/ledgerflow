import { execSync } from "node:child_process";
import path from "node:path";

export default function globalSetup() {
  // Reset + rebuild history through the real pipeline so every run starts from the same baseline.
  execSync("uv run python -m app.seed.demo_load", { cwd: path.resolve(__dirname, "../../backend"), stdio: "inherit" });
}
