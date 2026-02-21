# Cloudflare Setup & Domain Management

## Account Info
- **Account ID:** `211ffe93fdbdf4011e8b5a2bfaa782db`
- **Account email:** Ai_projects@unclesvf.com
- **Plan:** Free Website

## Authentication

### API Token (Full Access) — PRIMARY
- Stored in `C:\Users\scott\.claude\api-keys.json`
- Env var: `CLOUDFLARE_API_TOKEN`
- Permissions: Zone Edit, DNS Edit, SSL Edit, Pages Edit, Email Routing Edit, Page Rules Edit
- Token: `4-piraecyYDOuPr13hu4jXiHkx5Blm9w-2TQxm8t`
- Can create zones, manage DNS, deploy Pages, configure email routing

### API Token (DNS only) — BACKUP
- Token: `uwrvQ67Jpaf2St9n9wljgULzRvJrWwzW-YLWBxID`
- Permissions: Zone DNS Edit only

### Wrangler OAuth (full access)
- `wrangler login` opens browser for OAuth — user must click "Allow"
- Token stored in `C:\Users\scott\.wrangler\config\default.toml`
- Tokens expire hourly but have refresh_token with offline_access
- Scopes: account:read, pages:write, workers:write, zone:read, ssl_certs:write, and more
- **Does NOT include registrar scope** — domain registration must be done via dashboard

## Wrangler CLI
- **Version:** 4.63.0 (installed Feb 10, 2026)
- **Install:** `npm install -g wrangler`
- Config dir changed from `xdg.config\.wrangler` to `C:\Users\scott\.wrangler\`

## Domains

### forestfolkstudios.com (Feb 10, 2026)
- **Zone ID:** `d6d5e632c07f6d2b40c64f31ea5824ff`
- **Status:** Active
- **Nameservers:** `violet.ns.cloudflare.com` / `yahir.ns.cloudflare.com`
- **Registered through:** Cloudflare dashboard
- **DNS Records:**
  - `forestfolkstudios.com` → CNAME → `forest-folk-studios.pages.dev` (proxied)
  - `www.forestfolkstudios.com` → CNAME → `forest-folk-studios.pages.dev` (proxied)
- **Pages project:** `forest-folk-studios`
- **Pages dev URL:** https://forest-folk-studios.pages.dev
- **Local files:** `C:\Users\scott\forestfolkstudios\`
- **SSL:** Google CA, active
- **Deploy command:** `wrangler pages deploy "C:\Users\scott\forestfolkstudios" --project-name forest-folk-studios --branch main`

## The "Clean Slate" Migration Plan (Feb 8, 2026)

Scott has ~15 domains on **A2 Hosting** (12 years). Plan to migrate all to Cloudflare:

| Component | Destination | Cost |
|-----------|-------------|------|
| Domain registrar | Cloudflare (transfer all) | At-cost (~$9-10/yr .com) |
| DNS | Cloudflare free tier | Free |
| Site hosting | Cloudflare Pages | Free |
| Email | Cloudflare Email Routing → scott@unclesvf.com | Free |

**Key decisions:**
- Not attached to WordPress — all sites getting complete overhaul
- Simple static sites, no databases, no PHP
- Deploy from terminal with `wrangler pages deploy`
- Eliminates A2 monthly bill, WordPress maintenance, cPanel

**Status:** forestfolkstudios.com + unclesvf.com migrated. ~18 domains remaining on A2.

### unclesvf.com (Feb 10, 2026) — MIGRATED from A2
- **Zone ID:** `0f9d2bd341ff1f7900287c1beabf1550`
- **Status:** Active
- **Nameservers:** `violet.ns.cloudflare.com` / `yahir.ns.cloudflare.com`
- **Original registrar:** eNom (via A2 Hosting, purchased July 28, 2014)
- **Renewal:** $32.40/yr, expires 2026-07-29
- **DNS Records:**
  - `unclesvf.com` → CNAME → `unclesvf.pages.dev` (proxied) — website
  - `www.unclesvf.com` → CNAME → `unclesvf.pages.dev` (proxied) — website
  - `mail.unclesvf.com` → A → `104.218.12.65` (not proxied) — A2 mail server
  - `unclesvf.com` → MX 0 → `mail.unclesvf.com` — email stays on A2
  - `unclesvf.com` → TXT → SPF record for A2 email
- **Pages project:** `unclesvf`
- **Pages dev URL:** https://unclesvf.pages.dev
- **Local files:** `C:\Users\scott\unclesvf\`
- **Deploy command:** `wrangler pages deploy "C:\Users\scott\unclesvf" --project-name unclesvf --branch main`
- **Email:** Stays on A2 Hosting (104.218.12.65) via mail.unclesvf.com A record
- **IMPORTANT:** When website root is proxied CNAME, MX must point to a subdomain (mail.unclesvf.com) with its own A record to A2's IP — not the root domain
- **A2 Mail Server:** `mi3-ss110.a2hosting.com` (Exim 4.99.1) at 104.218.12.65 — SMTP verified working

## Email Migration Lessons Learned

**CRITICAL PATTERN** for migrating domains that have email on another host:
1. Root domain CNAME proxied through Cloudflare resolves to Cloudflare IPs, NOT the origin
2. MX records pointing to root domain will route email to Cloudflare Pages (broken!)
3. **Fix:** Create `mail.DOMAIN` as a non-proxied A record pointing directly to mail server IP
4. Point MX to `mail.DOMAIN` instead of root domain
5. Cloudflare may apply `_dc-mx` proxy rewrite to MX records — this can cause temporary resolution failures during DNS propagation
6. Always verify SMTP connectivity after migration: `curl -v telnet://MAIL_IP:25`

## A2 Hosting Domain Inventory (20 domains on cPanel)
1. asktheoldpeople.com
2. auntsvaluefarm.com (Main Domain)
3. carvingartists.com
4. crsac.com
5. grandmagrammar.com
6. lindabeachgirl.com
7. ncmtoken.com (redirects to ncmtokens.com)
8. ncmtokens.com
9. peak.zdevelopments.com
10. stansbeach.com
11. tokens7.com
12. unclesvaluefarm.co
13. unclesvaluefarm.com
14. unclesvaluefarm.info
15. unclesvaluefarm.net
16. unclesvaluefarm.org
17. unclesvf.com → MIGRATED to Cloudflare
18. vatra.witcheswonders.com
19. witcheswonders.com
20. zdevelopments.com

## A2 Hosting Nameserver Change Process
- **NOT in cPanel** (port 2083) — that's for hosting files/email
- Go to **hosting.com** client area (formerly my.a2hosting.com)
- Navigate: Domains → click domain → "Update Nameservers" button
- Must **unlock domain first** (Lock/Unlock button)
- Watch for **trailing spaces** in nameserver fields — causes silent errors

## Useful API Commands

```bash
# List all zones
curl -s "https://api.cloudflare.com/client/v4/zones" \
  -H "Authorization: Bearer 4-piraecyYDOuPr13hu4jXiHkx5Blm9w-2TQxm8t" | python -m json.tool

# List DNS records for a zone
curl -s "https://api.cloudflare.com/client/v4/zones/ZONE_ID/dns_records" \
  -H "Authorization: Bearer 4-piraecyYDOuPr13hu4jXiHkx5Blm9w-2TQxm8t" | python -m json.tool

# Add CNAME record
curl -s -X POST "https://api.cloudflare.com/client/v4/zones/ZONE_ID/dns_records" \
  -H "Authorization: Bearer 4-piraecyYDOuPr13hu4jXiHkx5Blm9w-2TQxm8t" \
  -H "Content-Type: application/json" \
  --data '{"type":"CNAME","name":"example.com","content":"project.pages.dev","proxied":true}'

# Deploy to Pages
wrangler pages deploy "C:\path\to\site" --project-name PROJECT_NAME --branch main
```

## Chrome Extension Note
- Upstream fix for Windows named pipe bug is now in cli.js (as of Feb 10 update)
- The patch script `patch-chrome-mcp.js` reports "already patched" because the fix is native
- Extension still had connection issues on Feb 10 — may be Chrome/extension restart needed
