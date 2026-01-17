#!/bin/bash
# Deploy script for Cloudflare with D1 and KV bindings
# Discovers resource IDs and updates wrangler.toml before deploying

set -e

echo "🔍 Looking up D1 database ID for 'overlap-db'..."
D1_ID=$(npx wrangler d1 list --json 2>/dev/null | node -pe "
  JSON.parse(require('fs').readFileSync(0,'utf8'))
    .find(d => d.name === 'overlap-db')?.uuid || ''
" 2>/dev/null || echo "")

if [ -z "$D1_ID" ]; then
  echo "❌ Could not find D1 database 'overlap-db'"
  exit 1
fi
echo "✅ Found D1 database: $D1_ID"

echo "🔍 Looking up KV namespace..."
KV_ID=$(npx wrangler kv:namespace list --json 2>/dev/null | node -pe "
  JSON.parse(require('fs').readFileSync(0,'utf8'))
    .find(n => n.title === 'overlap' || n.title.toLowerCase().includes('session'))?.id || ''
" 2>/dev/null || echo "")

if [ -z "$KV_ID" ]; then
  echo "❌ Could not find KV namespace"
  exit 1
fi
echo "✅ Found KV namespace: $KV_ID"

echo "📝 Updating wrangler.toml with resource IDs..."
# Use node to safely update wrangler.toml
node << EOF
const fs = require('fs');
let toml = fs.readFileSync('wrangler.toml', 'utf8');

// Add database_id if not present
if (!toml.includes('database_id')) {
  toml = toml.replace(
    /database_name = "overlap-db"/,
    'database_name = "overlap-db"\ndatabase_id = "${D1_ID}"'
  );
}

// Add KV id if not present
if (!toml.includes('id = "') || !toml.match(/\[\[kv_namespaces\]\][^[]*id = "/)) {
  toml = toml.replace(
    /\[\[kv_namespaces\]\]\s*\nbinding = "SESSION"/,
    '[[kv_namespaces]]\nbinding = "SESSION"\nid = "${KV_ID}"'
  );
}

fs.writeFileSync('wrangler.toml', toml);
console.log('✅ Updated wrangler.toml');
EOF

echo "🚀 Deploying to Cloudflare..."
npx wrangler deploy

echo "✅ Deployment complete!"
