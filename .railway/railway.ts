import { defineRailway, github, postgres, preserve, project, service, volume } from "railway/iac";

export default defineRailway(() => {
  const crmaffbot = github("dicee38/crmaffbot");

  const Postgres = postgres("Postgres", { region: "iad" });
  const postgresVolume = volume("postgres-volume", {
    alerts: { usage: { "100": {}, "80": {}, "95": {} } },
    allowOnlineResize: true,
    region: "iad",
    sizeMB: 500,
  });

  // uv workspace needs the whole repo (root pyproject.toml resolves the `shared` package),
  // so both services build from the repo root — there's no per-service subdirectory.
  const backend = service("backend", {
    source: crmaffbot,
    replicas: { iad: 1 },
    build: "pip install uv && uv sync --frozen",
    start:
      "uv run --package backend alembic -c backend/alembic.ini upgrade head && uv run --package backend uvicorn backend.main:app --host 0.0.0.0 --port $PORT",
    env: {
      DATABASE_URL: Postgres.env.DATABASE_URL,
      BOT_TOKEN: preserve(),
      INTERNAL_API_SECRET: preserve(),
      AFFILIATE_WEBHOOK_SECRET: preserve(),
      LARGE_DEPOSIT_THRESHOLD: "1000",
      DIGEST_HOUR_UTC: "6",
      IDLE_DAYS_THRESHOLD: "3",
    },
  });

  const bot = service("bot", {
    source: crmaffbot,
    replicas: { iad: 1 },
    build: "pip install uv && uv sync --frozen",
    start: "uv run --package bot python -m bot.main",
    env: {
      BOT_TOKEN: preserve(),
      INTERNAL_API_SECRET: preserve(),
      // Set once backend's public domain is generated (railway domain --service backend):
      // BACKEND_URL=https://<backend-domain>, MINIAPP_URL=https://<backend-domain>/miniapp/
      BACKEND_URL: preserve(),
      MINIAPP_URL: preserve(),
    },
  });

  return project("crmaffbot", {
    resources: [bot, backend, Postgres, postgresVolume],
  });
});
