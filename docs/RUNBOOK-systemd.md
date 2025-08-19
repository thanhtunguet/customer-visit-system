# Runbook: systemd deployment

- Path assumption: repo at `/home/ubuntu/face-recognition` (adjust service WorkingDirectory if different)
- Install Python venvs: `bash scripts/prod/setup_venvs.sh /home/ubuntu/face-recognition`
- Install systemd units: `sudo bash scripts/prod/install_systemd.sh`
- Configure env: `sudoedit /etc/face/face.env`
- Start/enable:
  - `sudo systemctl start face-api face-worker face-web`
  - `sudo systemctl enable face-api face-worker face-web`
- Logs:
  - `journalctl -u face-api -f`
  - `journalctl -u face-worker -f`
  - `journalctl -u face-web -f`

Notes:
- Web service runs `vite preview` for static serving; replace with nginx for production hardening if needed.
- Provide RS256 keys via env for JWT in production.
- Database/Milvus/MinIO endpoints should be reachable and configured via env.

