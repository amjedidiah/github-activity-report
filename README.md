# GitHub Activity Report

Generate comprehensive GitHub activity reports showing commits, PRs, issues, reviews, and comments.

## Quick Test

```bash
./github_report.py --test
```

## Quick Start

**1. Install dependencies:**

```bash
pip install -r requirements.txt
```

**2. Get credentials:**

- Token: [github.com/settings/tokens/new](https://github.com/settings/tokens/new) (scopes: `repo`, `read:user`)
- Username: Your GitHub username

**3. Set environment variables:**

Create a `.env` file:

```bash
GITHUB_TOKEN=your_token_here
GITHUB_USERNAME=your_username
```

Or set environment variables:

```bash
export GITHUB_TOKEN='your_token_here'
export GITHUB_USERNAME='your_username'
```

**4. Test connection (optional):**

```bash
./github_report.py --test
```

**5. Generate report:**

```bash
./github_report.py
```

## Usage

```bash
# Basic usage (last 7 days, prints to console)
./github_report.py

# Quick presets
./github_report.py --period day        # Last 24 hours
./github_report.py --period 3days      # Last 3 days
./github_report.py --period week       # Last 7 days
./github_report.py --period 2weeks     # Last 14 days
./github_report.py --period month      # Last 30 days

# Custom duration
./github_report.py --days 45           # Last 45 days
./github_report.py --days 90           # Quarterly review

# Save to file
./github_report.py --period month --output reports/monthly.md

# Different formats
./github_report.py --format html --output report.html
./github_report.py --period week --format text
```

## Options

```bash
--token TOKEN       GitHub token (or set GITHUB_TOKEN env var)
--username USER     GitHub username (or set GITHUB_USERNAME env var)
--period PRESET     Quick preset: day|3days|week|2weeks|month
--days N            Custom number of days (overrides --period)
--format FORMAT     Output: markdown|html|text (default: markdown)
--output FILE       Save to file instead of printing
--test              Test connection and credentials
```

**Default:** 7 days (1 week) if neither `--period` nor `--days` is specified.

## Automation

Run reports automatically with cron:

```bash
# Edit crontab
crontab -e

# Add this line (runs every Friday at 9 AM)
0 9 * * 5 cd /path/to/reports && python3 github_report.py --output reports/$(date +\%Y-\%m-\%d).md
```

## Output Example

```markdown
# GitHub Activity Report

**Developer:** username
**Period:** November 13, 2025 - November 20, 2025

## Executive Summary
- Total Commits: 47
- Pull Requests Opened: 5
- Pull Requests Merged: 4
- Pull Requests Reviewed: 3
- Issues Opened: 2
- Issues Closed: 3
```

## Troubleshooting

### "Error: GitHub token is required"

- Set `GITHUB_TOKEN` environment variable or use `--token` flag

### "No GitHub activity found"

- Check your username is correct
- Verify you have activity in the time period
- Ensure token has correct scopes (`repo`, `read:user`)

### Rate Limiting

- GitHub API: 5,000 requests/hour for authenticated requests
- Reduce `--days` parameter if hitting limits

---
