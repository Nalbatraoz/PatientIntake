module.exports = {
  apps: [
    {
      name: "patient-intake",
      cwd: "/home/ec2-user/PatientIntake",
      script: "/home/ec2-user/PatientIntake/.venv/bin/python",
      args: "-m api.main",
      interpreter: "none",
      instances: 1,
      autorestart: true,
      max_memory_restart: "1G",
      env: {
        FLASK_HOST: "0.0.0.0",
        FLASK_PORT: "5001",
        APP_BASE_PATH: "/patient-intake",
        FLASK_DEBUG: "0",

        SUBMISSIONS_PASSWORD: "admin123",

        GEMINI_API_KEY: "AIzaSyC8PnvnFq59tiIKWIGASGjrhhXKfrvK7z8",
        OPENAI_API_KEY: "your_openai_key",
        OPENFDA_API_KEY: "B3vNhd8V6XSA53joQxhvluOTcoKoAGszou7D6tf9",
        DRUGBANK_API_KEY: "",

        DB_PATH: "/home/ec2-user/PatientIntake/intake.db",
        UPLOAD_DIR: "/home/ec2-user/PatientIntake/uploads",
        RAG_SOURCE_DIR: "/home/ec2-user/PatientIntake/data/rag_files",
        RAG_CHROMA_DIR: "/home/ec2-user/PatientIntake/chroma_db"
      }
    }
  ]
};
