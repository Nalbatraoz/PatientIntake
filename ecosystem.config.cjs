const fs = require("fs");
const path = require("path");

const appDir = "/home/ec2-user/PatientIntake";

function loadDotEnv(filePath) {
  if (!fs.existsSync(filePath)) {
    return {};
  }

  return fs
    .readFileSync(filePath, "utf8")
    .split(/\r?\n/)
    .reduce((env, line) => {
      const trimmed = line.trim();
      if (!trimmed || trimmed.startsWith("#")) {
        return env;
      }

      const separatorIndex = trimmed.indexOf("=");
      if (separatorIndex === -1) {
        return env;
      }

      const key = trimmed.slice(0, separatorIndex).trim();
      let value = trimmed.slice(separatorIndex + 1).trim();
      if (
        (value.startsWith('"') && value.endsWith('"')) ||
        (value.startsWith("'") && value.endsWith("'"))
      ) {
        value = value.slice(1, -1);
      }

      env[key] = value;
      return env;
    }, {});
}

const fileEnv = loadDotEnv(path.join(appDir, ".env"));

module.exports = {
  apps: [
    {
      name: "patient-intake",
      cwd: appDir,
      script: path.join(appDir, ".venv/bin/python"),
      args: "-m api.main",
      interpreter: "none",
      instances: 1,
      autorestart: true,
      max_memory_restart: "1G",
      env: {
        FLASK_HOST: "127.0.0.1",
        FLASK_PORT: "5001",
        APP_BASE_PATH: "/patient-intake",
        FLASK_DEBUG: "0",
        DB_PATH: path.join(appDir, "intake.db"),
        UPLOAD_DIR: path.join(appDir, "uploads"),
        RAG_SOURCE_DIR: path.join(appDir, "data/rag_files"),
        RAG_CHROMA_DIR: path.join(appDir, "chroma_db"),
        ...fileEnv,
      }
    }
  ]
};
