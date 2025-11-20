#!/usr/bin/env python3
"""
GitHub Activity Report Generator
Generates a comprehensive summary of GitHub activities for professional reporting.
"""

import os
import sys
from datetime import datetime, timedelta
from typing import Dict, List, Any
from pathlib import Path
import requests
from collections import defaultdict
import argparse


# GitHub API datetime format constant
GITHUB_DATETIME_FORMAT = '%Y-%m-%dT%H:%M:%SZ'



class GitHubActivityReporter:
    """Generate GitHub activity reports."""
    
    def __init__(self, github_token: str, username: str):
        """
        Initialize the GitHub Activity Reporter.
        
        Args:
            github_token: GitHub personal access token
            username: GitHub username to track
        """
        self.github_token = github_token
        self.username = username
        self.headers = {
            'Authorization': f'token {github_token}',
            'Accept': 'application/vnd.github.v3+json'
        }
        self.base_url = 'https://api.github.com'
    
    def _make_request(self, endpoint: str, params: Dict = None) -> Any:
        """Make a request to the GitHub API."""
        url = f"{self.base_url}/{endpoint}"
        try:
            response = requests.get(url, headers=self.headers, params=params)
            response.raise_for_status()
            return response.json()
        except requests.exceptions.RequestException as e:
            print(f"Error making request to {endpoint}: {e}", file=sys.stderr)
            return None
    
    def _filter_events_by_date(self, page_events: List[Dict], since_date: datetime, 
                               events: List[Dict]) -> bool:
        """Filter events by date. Returns True if should continue fetching."""
        for event in page_events:
            event_date = datetime.strptime(event['created_at'], GITHUB_DATETIME_FORMAT)
            if event_date < since_date:
                return False
            events.append(event)
        return True
    
    def get_user_events(self, days_back: int = 7) -> List[Dict]:
        """
        Fetch user events from GitHub.
        
        Args:
            days_back: Number of days to look back
            
        Returns:
            List of event dictionaries
        """
        since_date = datetime.now() - timedelta(days=days_back)
        events = []
        
        for page in range(1, 11):  # Limit to 10 pages (300 events)
            endpoint = f"users/{self.username}/events"
            params = {'page': page, 'per_page': 100}
            page_events = self._make_request(endpoint, params)
            
            if not page_events:
                break
            
            if not self._filter_events_by_date(page_events, since_date, events):
                break
        
        return events
    
    def get_commits_by_repo(self, days_back: int = 7) -> Dict[str, List[Dict]]:
        """Get commits grouped by repository."""
        commits_by_repo = defaultdict(list)
        since_date = (datetime.now() - timedelta(days=days_back)).isoformat()
        
        # Get list of repositories
        repos_endpoint = f"users/{self.username}/repos"
        repos = self._make_request(repos_endpoint, {'per_page': 100})
        
        if not repos:
            return commits_by_repo
        
        for repo in repos:
            repo_name = repo['full_name']
            commits_endpoint = f"repos/{repo_name}/commits"
            params = {
                'author': self.username,
                'since': since_date,
                'per_page': 100
            }
            commits = self._make_request(commits_endpoint, params)
            
            if commits:
                commits_by_repo[repo_name].extend(commits)
        
        return commits_by_repo
    
    def _process_push_event(self, event: Dict, repo_name: str, summary: Dict) -> None:
        """Process PushEvent and update summary."""
        commits = event['payload'].get('commits', [])
        summary['commits'] += len(commits)
        for commit in commits:
            summary['commit_details'].append({
                'repo': repo_name,
                'sha': commit['sha'][:7],
                'message': commit['message'].split('\n')[0],
                'timestamp': event['created_at']
            })
    
    def _add_item_details(self, summary: Dict, counter_key: str, details_key: str,
                          item_data: Dict) -> None:
        """Helper to add item details to summary (reduces duplication)."""
        summary[counter_key] += 1
        summary[details_key].append(item_data)
    
    def _process_pr_event(self, event: Dict, repo_name: str, summary: Dict) -> None:
        """Process PullRequestEvent and update summary."""
        action = event['payload']['action']
        pr = event['payload']['pull_request']
        
        item_data = {
            'repo': repo_name,
            'title': pr.get('title', 'N/A'),
            'number': pr.get('number', 'N/A'),
            'timestamp': event['created_at']
        }
        
        if action == 'opened':
            item_data['action'] = 'opened'
            self._add_item_details(summary, 'pull_requests_opened', 'pr_details', item_data)
        elif action == 'closed' and pr.get('merged'):
            item_data['action'] = 'merged'
            self._add_item_details(summary, 'pull_requests_merged', 'pr_details', item_data)
    
    def _process_review_event(self, event: Dict, repo_name: str, summary: Dict) -> None:
        """Process PullRequestReviewEvent and update summary."""
        summary['pull_requests_reviewed'] += 1
        pr = event['payload']['pull_request']
        summary['review_details'].append({
            'repo': repo_name,
            'pr_title': pr.get('title', 'N/A'),
            'pr_number': pr.get('number', 'N/A'),
            'timestamp': event['created_at']
        })
    
    def _process_issue_event(self, event: Dict, repo_name: str, summary: Dict) -> None:
        """Process IssuesEvent and update summary."""
        action = event['payload']['action']
        issue = event['payload']['issue']
        
        item_data = {
            'repo': repo_name,
            'title': issue.get('title', 'N/A'),
            'number': issue.get('number', 'N/A'),
            'timestamp': event['created_at']
        }
        
        if action == 'opened':
            item_data['action'] = 'opened'
            self._add_item_details(summary, 'issues_opened', 'issue_details', item_data)
        elif action == 'closed':
            item_data['action'] = 'closed'
            self._add_item_details(summary, 'issues_closed', 'issue_details', item_data)
    
    def summarize_events(self, events: List[Dict]) -> Dict[str, Any]:
        """
        Summarize events into categories.
        
        Returns:
            Dictionary with categorized activity counts
        """
        summary = {
            'commits': 0,
            'pull_requests_opened': 0,
            'pull_requests_merged': 0,
            'pull_requests_reviewed': 0,
            'issues_opened': 0,
            'issues_closed': 0,
            'comments': 0,
            'repos': set(),
            'commit_details': [],
            'pr_details': [],
            'issue_details': [],
            'review_details': []
        }
        
        event_handlers = {
            'PushEvent': self._process_push_event,
            'PullRequestEvent': self._process_pr_event,
            'PullRequestReviewEvent': self._process_review_event,
            'IssuesEvent': self._process_issue_event
        }
        
        for event in events:
            event_type = event['type']
            repo_name = event['repo']['name']
            summary['repos'].add(repo_name)
            
            if event_type in event_handlers:
                event_handlers[event_type](event, repo_name, summary)
            elif event_type in ['IssueCommentEvent', 'CommitCommentEvent', 
                               'PullRequestReviewCommentEvent']:
                summary['comments'] += 1
        
        return summary
    
    def generate_report(self, days_back: int = 7, output_format: str = 'markdown', 
                       company: str = 'your company') -> str:
        """
        Generate the activity report.
        
        Args:
            days_back: Number of days to include in the report
            output_format: Format of the report ('markdown', 'text', or 'html')
            company: Company name for report footer
            
        Returns:
            Formatted report string
        """
        end_date = datetime.now()
        start_date = end_date - timedelta(days=days_back)
        
        print(f"Fetching GitHub activities for {self.username}...")
        events = self.get_user_events(days_back)
        
        if not events:
            return "No GitHub activity found for the specified period."
        
        summary = self.summarize_events(events)
        
        if output_format == 'markdown':
            return self._format_markdown_report(start_date, end_date, summary, company)
        elif output_format == 'html':
            return self._format_html_report(start_date, end_date, summary, company)
        else:
            return self._format_text_report(start_date, end_date, summary, company)
    
    def _add_markdown_header(self, start_date: datetime, end_date: datetime) -> List[str]:
        """Generate markdown header section."""
        return [
            "# GitHub Activity Report",
            f"\n**Developer:** {self.username}",
            f"**Period:** {start_date.strftime('%B %d, %Y')} - {end_date.strftime('%B %d, %Y')}",
            f"**Generated:** {end_date.strftime('%B %d, %Y at %I:%M %p')}",
            "\n---\n"
        ]
    
    def _add_markdown_summary(self, summary: Dict) -> List[str]:
        """Generate markdown executive summary section."""
        return [
            "## Executive Summary\n",
            f"- **Total Commits:** {summary['commits']}",
            f"- **Pull Requests Opened:** {summary['pull_requests_opened']}",
            f"- **Pull Requests Merged:** {summary['pull_requests_merged']}",
            f"- **Pull Requests Reviewed:** {summary['pull_requests_reviewed']}",
            f"- **Issues Opened:** {summary['issues_opened']}",
            f"- **Issues Closed:** {summary['issues_closed']}",
            f"- **Comments Made:** {summary['comments']}",
            f"- **Active Repositories:** {len(summary['repos'])}"
        ]
    
    def _add_markdown_repos(self, repos: set) -> List[str]:
        """Generate markdown repositories section."""
        if not repos:
            return []
        return ["\n## Active Repositories\n"] + [f"- `{repo}`" for repo in sorted(repos)]
    
    def _add_markdown_commits(self, commit_details: List[Dict]) -> List[str]:
        """Generate markdown commits section."""
        if not commit_details:
            return []
        
        lines = ["\n## Commits\n"]
        commits_by_repo = defaultdict(list)
        for commit in commit_details:
            commits_by_repo[commit['repo']].append(commit)
        
        for repo in sorted(commits_by_repo.keys()):
            lines.append(f"\n### {repo}")
            for commit in commits_by_repo[repo][:20]:
                timestamp = datetime.strptime(commit['timestamp'], GITHUB_DATETIME_FORMAT)
                lines.append(f"- `{commit['sha']}` {commit['message']} "
                           f"*({timestamp.strftime('%b %d, %I:%M %p')})*")
        return lines
    
    def _format_markdown_item(self, item: Dict, item_type: str, 
                              emoji_map: Dict[str, str]) -> List[str]:
        """Format a single PR or Issue for markdown (reduces duplication)."""
        timestamp = datetime.strptime(item['timestamp'], GITHUB_DATETIME_FORMAT)
        action_emoji = emoji_map.get(item['action'], '•')
        return [
            f"{action_emoji} **{item['action'].title()}** {item_type} #{item['number']}: {item['title']}",
            f"   - Repository: `{item['repo']}`",
            f"   - Date: {timestamp.strftime('%b %d, %Y at %I:%M %p')}\n"
        ]
    
    def _add_markdown_prs(self, pr_details: List[Dict]) -> List[str]:
        """Generate markdown pull requests section."""
        if not pr_details:
            return []
        
        lines = ["\n## Pull Requests\n"]
        emoji_map = {'opened': '🟢', 'merged': '🟣'}
        for pr in pr_details:
            lines.extend(self._format_markdown_item(pr, 'PR', emoji_map))
        return lines
    
    def _add_markdown_issues(self, issue_details: List[Dict]) -> List[str]:
        """Generate markdown issues section."""
        if not issue_details:
            return []
        
        lines = ["\n## Issues\n"]
        emoji_map = {'opened': '🔵', 'closed': '✅'}
        for issue in issue_details:
            lines.extend(self._format_markdown_item(issue, 'Issue', emoji_map))
        return lines
    
    def _add_markdown_reviews(self, review_details: List[Dict]) -> List[str]:
        """Generate markdown reviews section."""
        if not review_details:
            return []
        
        lines = ["\n## Code Reviews\n"]
        for review in review_details:
            timestamp = datetime.strptime(review['timestamp'], GITHUB_DATETIME_FORMAT)
            lines.extend([
                f"- Reviewed PR #{review['pr_number']}: {review['pr_title']}",
                f"  - Repository: `{review['repo']}`",
                f"  - Date: {timestamp.strftime('%b %d, %Y at %I:%M %p')}\n"
            ])
        return lines
    
    def _format_markdown_report(self, start_date: datetime, end_date: datetime, 
                                summary: Dict, company: str) -> str:
        """Format report as Markdown."""
        report = []
        report.extend(self._add_markdown_header(start_date, end_date))
        report.extend(self._add_markdown_summary(summary))
        report.extend(self._add_markdown_repos(summary['repos']))
        report.extend(self._add_markdown_commits(summary['commit_details']))
        report.extend(self._add_markdown_prs(summary['pr_details']))
        report.extend(self._add_markdown_issues(summary['issue_details']))
        report.extend(self._add_markdown_reviews(summary['review_details']))
        report.extend(["\n---\n", f"\n*Report generated automatically for {company}*"])
        
        return '\n'.join(report)
    
    def _format_text_report(self, start_date: datetime, end_date: datetime, 
                           summary: Dict, company: str) -> str:
        """Format report as plain text."""
        report = []
        report.append("=" * 70)
        report.append("GITHUB ACTIVITY REPORT")
        report.append("=" * 70)
        report.append(f"\nDeveloper: {self.username}")
        report.append(f"Period: {start_date.strftime('%B %d, %Y')} - {end_date.strftime('%B %d, %Y')}")
        report.append(f"Generated: {end_date.strftime('%B %d, %Y at %I:%M %p')}")
        report.append("\n" + "-" * 70)
        
        report.append("\nEXECUTIVE SUMMARY")
        report.append("-" * 70)
        report.append(f"Total Commits: {summary['commits']}")
        report.append(f"Pull Requests Opened: {summary['pull_requests_opened']}")
        report.append(f"Pull Requests Merged: {summary['pull_requests_merged']}")
        report.append(f"Pull Requests Reviewed: {summary['pull_requests_reviewed']}")
        report.append(f"Issues Opened: {summary['issues_opened']}")
        report.append(f"Issues Closed: {summary['issues_closed']}")
        report.append(f"Comments Made: {summary['comments']}")
        report.append(f"Active Repositories: {len(summary['repos'])}")
        
        if summary['repos']:
            report.append("\n" + "-" * 70)
            report.append("ACTIVE REPOSITORIES")
            report.append("-" * 70)
            for repo in sorted(summary['repos']):
                report.append(f"  - {repo}")
        
        report.append("\n" + "=" * 70)
        report.append(f"Report generated for {company}")
        report.append("=" * 70)
        
        return '\n'.join(report)
    
    def _get_html_styles(self) -> str:
        """Return CSS styles for HTML report."""
        return """
        body {
            font-family: -apple-system, BlinkMacSystemFont, 'Segoe UI', Roboto, Oxygen, Ubuntu, Cantarell, sans-serif;
            line-height: 1.6;
            max-width: 900px;
            margin: 0 auto;
            padding: 20px;
            background-color: #f5f5f5;
        }
        .container {
            background: white;
            padding: 30px;
            border-radius: 8px;
            box-shadow: 0 2px 4px rgba(0,0,0,0.1);
        }
        h1 {
            color: #24292e;
            border-bottom: 3px solid #0366d6;
            padding-bottom: 10px;
        }
        h2 {
            color: #0366d6;
            margin-top: 30px;
        }
        .meta {
            color: #586069;
            margin-bottom: 20px;
        }
        .summary {
            display: grid;
            grid-template-columns: repeat(auto-fit, minmax(200px, 1fr));
            gap: 15px;
            margin: 20px 0;
        }
        .metric {
            background: #f6f8fa;
            padding: 15px;
            border-radius: 6px;
            border-left: 4px solid #0366d6;
        }
        .metric-value {
            font-size: 24px;
            font-weight: bold;
            color: #24292e;
        }
        .metric-label {
            font-size: 12px;
            color: #586069;
            text-transform: uppercase;
        }
        .repo-list {
            background: #f6f8fa;
            padding: 15px;
            border-radius: 6px;
            font-family: 'Courier New', monospace;
        }
        .footer {
            margin-top: 30px;
            padding-top: 20px;
            border-top: 2px solid #e1e4e8;
            text-align: center;
            color: #586069;
            font-style: italic;
        }
        """
    
    def _get_html_metric(self, value: int, label: str) -> str:
        """Generate a single metric card for HTML report."""
        return f"""
            <div class="metric">
                <div class="metric-value">{value}</div>
                <div class="metric-label">{label}</div>
            </div>"""
    
    def _get_html_summary(self, summary: Dict) -> str:
        """Generate HTML summary section."""
        metrics = [
            (summary['commits'], 'Total Commits'),
            (summary['pull_requests_opened'], 'PRs Opened'),
            (summary['pull_requests_merged'], 'PRs Merged'),
            (summary['pull_requests_reviewed'], 'PRs Reviewed'),
            (summary['issues_opened'], 'Issues Opened'),
            (summary['issues_closed'], 'Issues Closed'),
            (summary['comments'], 'Comments'),
            (len(summary['repos']), 'Active Repos')
        ]
        
        metric_html = ''.join([self._get_html_metric(value, label) for value, label in metrics])
        
        return f"""
        <h2>Executive Summary</h2>
        <div class="summary">{metric_html}
        </div>"""
    
    def _format_html_report(self, start_date: datetime, end_date: datetime, 
                           summary: Dict, company: str) -> str:
        """Format report as HTML."""
        styles = self._get_html_styles()
        summary_html = self._get_html_summary(summary)
        repos_html = '<br>'.join(['• ' + repo for repo in sorted(summary['repos'])])
        
        html = f"""<!DOCTYPE html>
<html lang="en">
<head>
    <meta charset="UTF-8">
    <title>GitHub Activity Report</title>
    <style>{styles}</style>
</head>
<body>
    <div class="container">
        <h1>GitHub Activity Report</h1>
        <div class="meta">
            <p><strong>Developer:</strong> {self.username}</p>
            <p><strong>Period:</strong> {start_date.strftime('%B %d, %Y')} - {end_date.strftime('%B %d, %Y')}</p>
            <p><strong>Generated:</strong> {end_date.strftime('%B %d, %Y at %I:%M %p')}</p>
        </div>
        {summary_html}
        <h2>Active Repositories</h2>
        <div class="repo-list">{repos_html}</div>
        <div class="footer">Report generated automatically for {company}</div>
    </div>
</body>
</html>"""
        return html


def test_connection(token: str, username: str) -> bool:
    """Test GitHub API connection and credentials."""
    print("Testing GitHub API connection...")
    
    headers = {
        'Authorization': f'token {token}',
        'Accept': 'application/vnd.github.v3+json'
    }
    
    try:
        response = requests.get(
            f'https://api.github.com/users/{username}',
            headers=headers
        )
        
        if response.status_code == 200:
            user_data = response.json()
            print("✅ Connected successfully")
            print(f"   User: {user_data.get('name', username)}")
            print(f"   Public repos: {user_data.get('public_repos', 0)}")
            rate_limit = response.headers.get('X-RateLimit-Remaining')
            rate_total = response.headers.get('X-RateLimit-Limit')
            print(f"   API rate limit: {rate_limit}/{rate_total} remaining")
            return True
        elif response.status_code == 401:
            print("❌ Invalid token. Check your GITHUB_TOKEN")
            return False
        elif response.status_code == 404:
            print("❌ User not found. Check your GITHUB_USERNAME")
            return False
        else:
            print(f"❌ API error: {response.status_code}")
            return False
    except Exception as e:
        print(f"❌ Connection error: {e}")
        return False


def setup_argument_parser() -> argparse.ArgumentParser:
    """Setup and return the argument parser."""
    parser = argparse.ArgumentParser(
        description='Generate a GitHub activity report for professional documentation.'
    )
    parser.add_argument(
        '--token',
        help='GitHub personal access token (or set GITHUB_TOKEN env var)',
        default=os.environ.get('GITHUB_TOKEN')
    )
    parser.add_argument(
        '--username',
        help='GitHub username (or set GITHUB_USERNAME env var)',
        default=os.environ.get('GITHUB_USERNAME')
    )
    parser.add_argument(
        '--period',
        choices=['day', '3days', 'week', '2weeks', 'month'],
        help='Time period preset: day(1), 3days, week(7), 2weeks(14), month(30)'
    )
    parser.add_argument(
        '--days',
        type=int,
        help='Custom number of days (overrides --period, default: 7)'
    )
    parser.add_argument(
        '--format',
        choices=['markdown', 'text', 'html'],
        default='markdown',
        help='Output format (default: markdown)'
    )
    parser.add_argument(
        '--output',
        help='Output file path (default: print to stdout)'
    )
    parser.add_argument(
        '--test',
        action='store_true',
        help='Test GitHub API connection and credentials'
    )
    parser.add_argument(
        '--company',
        default='your company',
        help='Company name for report footer (default: your company)'
    )
    return parser


def calculate_days(args) -> int:
    """Calculate number of days based on period or days argument."""
    period_map = {
        'day': 1,
        '3days': 3,
        'week': 7,
        '2weeks': 14,
        'month': 30
    }
    
    if args.days:
        return args.days
    elif args.period:
        return period_map[args.period]
    else:
        return 7  # Default to 1 week


def validate_credentials(token: str, username: str) -> None:
    """Validate required credentials and exit if missing."""
    if not token:
        print("Error: GitHub token is required. Set GITHUB_TOKEN environment variable "
              "or use --token flag.", file=sys.stderr)
        print("\nTo create a token, visit: https://github.com/settings/tokens", file=sys.stderr)
        sys.exit(1)
    
    if not username:
        print("Error: GitHub username is required. Set GITHUB_USERNAME environment variable "
              "or use --username flag.", file=sys.stderr)
        sys.exit(1)


def save_or_print_report(report: str, output_path: str = None) -> None:
    """Save report to file or print to stdout."""
    if output_path:
        path = Path(output_path)
        path.parent.mkdir(parents=True, exist_ok=True)
        
        with open(output_path, 'w', encoding='utf-8') as f:
            f.write(report)
        print(f"Report successfully generated: {output_path}")
    else:
        print(report)


def main():
    """Main entry point for the script."""
    parser = setup_argument_parser()
    args = parser.parse_args()
    
    days = calculate_days(args)
    validate_credentials(args.token, args.username)
    
    if args.test:
        success = test_connection(args.token, args.username)
        sys.exit(0 if success else 1)
    
    reporter = GitHubActivityReporter(args.token, args.username)
    report = reporter.generate_report(days, args.format, args.company)
    save_or_print_report(report, args.output)


if __name__ == '__main__':
    main()

