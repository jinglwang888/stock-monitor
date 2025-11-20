# Stock Monitor (Polygon-only)

Automated monitor for positions using exit rules (min hold days, drawdown, take-profit, trailing stop), powered by Polygon.io market data.

## Quick start (local)
1) Install deps
```bash
pip install -r requirements.txt
```
2) Copy `config/.env.example` to `config/.env` and fill your `POLYGON_API_KEY`:
```bash
cp config/.env.example config/.env
```
3) Put your positions in `data/my_current_holdings.csv` (see `data/examples/...`).
4) Run:
```bash
python src/monitor_polygon_positions.py
```

## GitHub Actions (scheduled runs)
`/.github/workflows/monitor.yml` runs the monitor on a weekday schedule.
Add `POLYGON_API_KEY` as a repository secret.

## File layout
- `src/monitor_polygon_positions.py` : core monitoring script (Polygon only)
- `data/my_current_holdings.csv`      : your live positions (gitignored)
- `data/examples/*.csv`               : templates (safe to commit)
- `config/.env`                       : your secrets (gitignored)

## Notes
- The script prints alerts to STDOUT. You can add email/Slack alerts later.
- GitHub Actions example creates a placeholder CSV; swap with your real data securely.
