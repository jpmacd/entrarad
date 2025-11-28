# Entrarad – FreeRADIUS to Microsoft Entra Bridge

Entrarad is a lightweight FastAPI service that lets FreeRADIUS authenticate user credentials against Microsoft Entra by using the Resource Owner Password Credentials (ROPC) flow. The repo ships both the HTTP API (`entrarad/`) and a FreeRADIUS container (`freeradius/`) that calls the API through the built‑in `rest` module. Together they give you a minimal “drop-in” bridge for network gear that only speaks PAP.

```
NAS/Firewall --PAP--> FreeRADIUS --REST--> Entrarad API --ROPC--> Microsoft Entra/Graph
```

## Repository Layout

| Path | Purpose |
| --- | --- |
| `entrarad/app.py` | FastAPI app that calls MSAL, validates the Graph token, and exposes `/validate_credentials`. |
| `entrarad/Dockerfile` | Slim Python image for running the API. |
| `freeradius/` | FreeRADIUS image with a REST auth module and opinionated `sites-available/default`. |
| `docker-compose.yml` | Builds both containers, wires secrets, and ensures FreeRADIUS waits for Entrarad health. |
| `entrarad.service` | Example Systemd unit for running only the API on bare metal with a Python venv. |

## How the Pieces Fit

1. A RADIUS client (NAS, VPN, etc.) sends a PAP Access-Request.
2. FreeRADIUS matches allowed realms in `freeradius/sites-available/default` and sets `Auth-Type := rest`.
3. The REST module POSTs `{ "username": "...", "password": "..." }` to `http://entrarad:5000/validate_credentials` with the shared bearer token header.
4. Entrarad uses MSAL’s ROPC flow to request a token via Microsoft Graph scopes, validates the token by calling `https://graph.microsoft.com/v1.0/me`, and returns 200/401/403 accordingly.
5. FreeRADIUS proxies the HTTP result back to the client as Access-Accept or Access-Reject.

## Prerequisites

- Docker & Docker Compose v2, or a Linux host capable of running the FastAPI service via Systemd.
- A Microsoft Entra tenant where username/password auth is still allowed for the users in scope.
- An Azure App Registration configured for ROPC and granted `User.Read` (or broader) Microsoft Graph permissions.
- A Conditional Access exclusion that skips MFA for the specific RADIUS client scenario.
- PAP support on every RADIUS client that will talk to FreeRADIUS (this project does not implement CHAP/EAP).

## Microsoft Entra Preparation

1. **Create an App Registration**
   - Platform type: `web` or `public client/native`.
   - Allow public client flows (Authentication -> “Allow public client flows”).
2. **Grant API permissions**
   - Add `Microsoft Graph > Delegated > User.Read` (minimum for the `/me` validation call).
   - Grant admin consent.
3. **Collect client values**
   - `Application (client) ID`
   - `Directory (tenant) ID`
   - A client secret created under “Certificates & secrets”.
4. **Allow username/password auth**
   - Users must have authentication methods that work with ROPC; no MFA challenge can be enforced.

You can optionally override the `AUTHORITY` environment variable if you need a specific login audience (e.g., national clouds).

## Secrets and Environment Variables

Entrarad reads values from environment variables (see `entrarad/app.py`). When you run with Docker Compose, those values come from files mounted as Docker secrets.

| Variable | Description |
| --- | --- |
| `CLIENT_ID` | App registration client ID. |
| `TENANT_ID` | Directory (tenant) ID. |
| `CLIENT_SECRET` | Client secret string. |
| `AUTHORITY` | Optional; defaults to `https://login.microsoftonline.com/{TENANT_ID}`. |
| `DEBUG` | `true/false` toggling verbose logging. |
| `TIMEOUT` | HTTP timeout (seconds) for Microsoft Graph validation calls. |
| `LOG_FILE_APP`, `LOG_FILE_UVICORN` | Paths where Entrarad writes structured logs. |

### Docker secrets

Create the `.secrets` directory in the repo root and place one value per file:

```bash
mkdir -p .secrets
printf '00000000-0000-0000-0000-000000000000' > .secrets/client_id.txt
printf '11111111-1111-1111-1111-111111111111' > .secrets/tenant_id.txt
printf 'your-client-secret' > .secrets/client_secret.txt
printf 'shared-rest-token' > .secrets/api_token.txt   # matches rest module Authorization header
```

The FreeRADIUS `rest` module uses `Authorization: Bearer <TOKEN>` as configured in `freeradius/mods-available/rest`. Keep the same value in `.secrets/api_token.txt`.

### FreeRADIUS configuration knobs

- `freeradius/clients.conf`: populate the RADIUS shared secret per client (the example uses `client localhost`).
- `freeradius/sites-available/default`: adjust the regex in the `authorize` section to match your accepted UPN suffixes or Realms.
- `freeradius/mods-available/rest`: change the Entrarad URL, add TLS, or adjust headers if you front the API with a proxy.

Rebuild the FreeRADIUS image whenever you change those files.

## Deploy with Docker Compose

1. **Clone the repo**
   ```bash
   git clone https://github.com/your-org/entrarad.git
   cd entrarad
   ```
2. **Install secrets**
   - Follow the `.secrets` instructions above.
3. **Build and launch**
   ```bash
   docker compose up -d --build
   ```
   - Entrarad exposes `127.0.0.1:5000`.
   - FreeRADIUS exposes UDP `1812` (auth) on the host. Modify the compose file if you also need accounting (`1813`).
4. **Verify**
   - `curl http://localhost:5000/healthcheck` → `200 OK` from Entrarad.
   - `docker logs entrarad-main-entrarad-1` for API logs.
   - `docker logs entrarad-main-freeradius-1` (or run `radiusd -X` inside the container) to watch Access-Request handling.

### Upgrading / redeploying

```bash
docker compose pull
docker compose up -d --build --force-recreate
```

## Bare-Metal / Systemd Deployment (Entrarad only)

If you already run FreeRADIUS elsewhere, you can deploy only the FastAPI service on a Linux host:

1. Copy `entrarad/` to `/opt/entrarad`, create a Python 3.11 virtual environment, and install requirements:
   ```bash
   cd /opt/entrarad
   python3 -m venv venv
   source venv/bin/activate
   pip install --upgrade pip
   pip install -r requirements.txt
   ```
2. Create `/opt/entrarad/.env` with the same variables described earlier (one per line: `KEY=value`).
3. Place `entrarad.service` in `/etc/systemd/system/`, adjust the `User`, `Group`, and `WorkingDirectory` if needed.
4. Enable and start the service:
   ```bash
   sudo systemctl daemon-reload
   sudo systemctl enable --now entrarad
   sudo systemctl status entrarad
   ```
5. Point your existing FreeRADIUS server’s REST module at the new HTTP endpoint.

## Use the Dockerfiles Individually

If you do not want the compose bundle, you can build and run the containers separately.

### Entrarad API container

```bash
docker build -t entrarad-api ./entrarad
cat <<'EOF' > entrarad.env
DEBUG=false
TIMEOUT=10
CLIENT_ID=00000000-0000-0000-0000-000000000000
TENANT_ID=11111111-1111-1111-1111-111111111111
CLIENT_SECRET=your-client-secret
AUTHORITY=https://login.microsoftonline.com/11111111-1111-1111-1111-111111111111
LOG_FILE_APP=/tmp/app.log
LOG_FILE_UVICORN=/tmp/uvicorn.log
EOF
docker run -d --name entrarad-api \
  --env-file entrarad.env \
  -p 5000:5000 \
  entrarad-api
```

### FreeRADIUS container

```bash
docker build -t entrarad-radius ./freeradius
docker run -d --name entrarad-radius \
  --env API_TOKEN=shared-rest-token \
  --link entrarad-api:entrarad \
  -p 1812:1812/udp \
  entrarad-radius
```

`--link` gives the container the hostname `entrarad`, matching the REST module’s default `connect_uri`. Replace it with a user-defined docker network or a static IP if you prefer. Update `freeradius/clients.conf` with the real RADIUS shared secret before building.

## API Overview

| Method | Path | Description |
| --- | --- | --- |
| `POST` | `/validate_credentials` | Body: `{ "username": "", "password": "" }`. Returns `200` on success, `401` when MSAL fails to acquire a token, `403` when the Graph validation call fails, `500` when anything else breaks. |
| `GET` | `/healthcheck` | Lightweight health probe used by Docker and any external monitoring. |

Both endpoints respond without a JSON payload; the HTTP status code is all FreeRADIUS needs.

## Security Considerations

- **PAP is inherently weak.** It uses salted MD5 and old crypto. You can’t make it safer.
- **Cloud-only + RADIUS doesn’t work.** You need hybrid with Microsoft’s NPS Extension for Entra. Tried it cloud-only; it just doesn’t fly.
- **Don’t send PAP over the internet.** Keep it on internal, trusted networks.
- **No MFA.** You’ll need a Conditional Access exclusion.
- **Uses ROPC.** Microsoft can drop it anytime.
- **No CHAP.** Its challenge-response model never exposes the real credential, so it won’t work here.

Beyond those fundamentals:
- Restrict access to the Entrarad HTTP port (only FreeRADIUS should talk to it).
- Rotate the REST bearer token and the RADIUS shared secrets regularly.
- Monitor the Entrarad logs for repeated `401/403` responses which can signal password spray attempts.

## Troubleshooting

- **MSAL errors / 401s**: Confirm the app registration allows public client flows and the credentials are correct.
- **403s**: Usually Graph denied access because the token validation call failed; check Conditional Access and licensing.
- **FreeRADIUS rejects username immediately**: Update the regex in `sites-available/default` so your realm is accepted.
- **Timeouts**: Increase the `TIMEOUT` env var or ensure the host has outbound internet for Microsoft Graph.

With those pieces in place you can front legacy network gear with a minimal bridge to Microsoft Entra while understanding exactly where the trade-offs live.
