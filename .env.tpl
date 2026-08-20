# Secrets manifest (see the infra skill). Local dev: op run --env-file=.env.tpl -- just run
# ASC refs point at the shared Apple Signing vault; op-project-bootstrap mints the SA with read on both.
NOTION_API_TOKEN=op://Notion Automations/Notion Automations ENV/NOTION_API_TOKEN
NOTION_WEBHOOK_SECRET=op://Notion Automations/Notion Automations ENV/NOTION_WEBHOOK_SECRET
ASC_KEY_ID=op://Apple Signing/App Store Connect API Key/key_id
ASC_ISSUER_ID=op://Apple Signing/App Store Connect API Key/issuer_id
ASC_P8_BASE64=op://Apple Signing/App Store Connect API Key/p8_base64
