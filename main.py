import os
import re
import sys
import logging
from github import Github, GithubException
import requests
import google.generativeai as genai

# Configure logging to show up in GitHub Actions
logging.basicConfig(
    level=logging.INFO,
    format='%(asctime)s - %(levelname)s - %(message)s'
)
logger = logging.getLogger(__name__)

# Output to GitHub Actions
def set_output(name, value):
    if 'GITHUB_OUTPUT' in os.environ:
        with open(os.environ['GITHUB_OUTPUT'], 'a') as fh:
            print(f'{name}={value}', file=fh)
    else:
        logger.info(f"Output: {name}={value}")

def parse_commit_message(msg):
    # Conventional commit regex
    first_line = msg.strip().split('\n')[0]
    match = re.match(r"^(build|chore|ci|docs|feat|fix|perf|refactor|revert|style|test)(?:\(([\w\-.]+)\))?(!)?: (.+)$", first_line)
    is_breaking = False
    if match and match.group(3) == '!':
        is_breaking = True
    if 'BREAKING CHANGE:' in msg:
        is_breaking = True
        
    if not match:
        return {'type': 'other', 'scope': None, 'description': first_line, 'is_breaking': is_breaking}
        
    return {
        'type': match.group(1),
        'scope': match.group(2),
        'description': match.group(4),
        'is_breaking': is_breaking
    }

def main():
    token = os.environ.get('INPUT_GITHUB-TOKEN')
    if not token:
        logger.error("github-token is required")
        sys.exit(1)
        
    target_dir = os.environ.get('INPUT_TARGET-DIRECTORY', '').strip()
    webhook_url = os.environ.get('INPUT_WEBHOOK-URL', '').strip()
    fallback_policy = os.environ.get('INPUT_FALLBACK-POLICY', 'patch').strip().lower()
    gemini_api_key = os.environ.get('INPUT_GEMINI-API-KEY', '').strip()
    
    repo_name = os.environ.get('GITHUB_REPOSITORY')
    sha = os.environ.get('GITHUB_SHA')
    
    if not repo_name or not sha:
        logger.error("GITHUB_REPOSITORY or GITHUB_SHA is missing.")
        sys.exit(1)
    
    g = Github(token)
    repo = g.get_repo(repo_name)
    
    prefix = target_dir.replace('/', '-') + '-v' if target_dir else 'v'
        
    # Get tags
    logger.info(f"Looking for tags with prefix: {prefix}")
    tags = list(repo.get_tags())
    relevant_tags = []
    
    for t in tags:
        if t.name.startswith(prefix):
            # Try to parse semantic version
            version_str = t.name[len(prefix):]
            try:
                parts = [int(x) for x in version_str.split('.')]
                if len(parts) == 3:
                    relevant_tags.append((parts, t))
            except ValueError:
                pass

    releases = list(repo.get_releases())
    release_tag_names = {r.tag_name for r in releases}
    
    valid_tags = []
    for parts, t in relevant_tags:
        if t.name in release_tag_names:
            valid_tags.append((parts, t))
        else:
            if t.commit.sha == sha:
                # This is the tag we are reconciling right now
                valid_tags.append((parts, t))
            else:
                # Orphaned tag on an older commit
                logger.warning(f"Found orphaned tag {t.name} on older commit {t.commit.sha}. Deleting ref.")
                try:
                    repo.get_git_ref(f"tags/{t.name}").delete()
                except GithubException as e:
                    logger.warning(f"Could not delete orphaned tag {t.name}: {e}")
                
    valid_tags.sort(key=lambda x: x[0], reverse=True)
    
    latest_tag = valid_tags[0][1] if valid_tags else None
    previous_tag = valid_tags[1][1] if len(valid_tags) > 1 else None
    current_version = valid_tags[0][0] if valid_tags else [0, 0, 0]
    
    # Idempotency check: Did it fail after tagging?
    if latest_tag and latest_tag.commit.sha == sha:
        logger.info(f"Latest tag {latest_tag.name} points to current HEAD ({sha}).")
        if latest_tag.name in release_tag_names:
            release = next((r for r in releases if r.tag_name == latest_tag.name), None)
            logger.info(f"Release {release.tag_name} already exists. Exiting cleanly.")
            set_output('new-version', latest_tag.name)
            set_output('release-url', release.html_url)
            sys.exit(0)
        else:
            logger.info("Release does not exist for the tag on HEAD. Resuming release creation.")
            base_tag = previous_tag
            target_version_name = latest_tag.name
            skip_tag_creation = True
    else:
        base_tag = latest_tag
        target_version_name = None # To be calculated
        skip_tag_creation = False

    logger.info(f"Base tag for comparison: {base_tag.name if base_tag else 'None'}")
    
    # Get commits
    if target_dir:
        logger.info(f"Filtering commits for directory: {target_dir}")
        commits_iterator = repo.get_commits(path=target_dir, sha=sha)
    else:
        commits_iterator = repo.get_commits(sha=sha)
        
    commits = []
    for c in commits_iterator:
        if base_tag and c.sha == base_tag.commit.sha:
            break
        commits.append(c)
        if not base_tag and len(commits) >= 100:
            logger.info("No base tag found. Limiting to 100 recent commits for the initial release.")
            break
        if len(commits) >= 500:
            logger.warning("Reached 500 commits limit. Truncating changelog.")
            break

    if not commits and not skip_tag_creation:
        logger.info("No commits found for the specified scope. Exiting.")
        set_output('new-version', f"{prefix}{current_version[0]}.{current_version[1]}.{current_version[2]}")
        sys.exit(0)
        
    # Analyze commits
    bump_type = None
    has_conventional = False
    parsed_commits = []
    
    for c in commits:
        msg = c.commit.message
        parsed = parse_commit_message(msg)
        parsed['sha'] = c.sha
        parsed['author'] = c.commit.author.name if c.commit.author else 'Unknown'
        parsed_commits.append(parsed)
        
        if parsed['type'] != 'other':
            has_conventional = True
            
        if parsed['is_breaking']:
            bump_type = 'major'
        elif parsed['type'] == 'feat' and bump_type != 'major':
            bump_type = 'minor'
        elif parsed['type'] == 'fix' and bump_type not in ['major', 'minor']:
            bump_type = 'patch'
            
    if not has_conventional:
        if fallback_policy == 'fail':
            logger.error("No conventional commits found and fallback-policy is 'fail'.")
            if webhook_url:
                payload = {"text": "❌ **Release Failed**: Non-compliant commits detected. Developers must use Conventional Commits."}
                requests.post(webhook_url, json=payload)
            sys.exit(1)
        elif fallback_policy == 'skip':
            logger.info("No conventional commits found and fallback-policy is 'skip'. Exiting gracefully.")
            set_output('new-version', f"{prefix}{current_version[0]}.{current_version[1]}.{current_version[2]}")
            sys.exit(0)
        else:
            logger.info("No conventional commits found. Defaulting to patch bump.")
            bump_type = 'patch'
    elif bump_type is None:
        bump_type = 'patch'
            
    if not skip_tag_creation:
        if bump_type == 'major':
            new_version = [current_version[0] + 1, 0, 0]
        elif bump_type == 'minor':
            new_version = [current_version[0], current_version[1] + 1, 0]
        else:
            new_version = [current_version[0], current_version[1], current_version[2] + 1]
            
        target_version_name = f"{prefix}{new_version[0]}.{new_version[1]}.{new_version[2]}"
        
        logger.info(f"Calculated next version: {target_version_name} (bump: {bump_type})")
        
        # Create tag
        logger.info(f"Creating tag {target_version_name} on {sha}")
        try:
            repo.create_git_ref(ref=f"refs/tags/{target_version_name}", sha=sha)
        except GithubException as e:
            if e.status == 422 and "Reference already exists" in e.data.get('message', ''):
                logger.warning(f"Tag {target_version_name} already exists. Assuming state reconciliation and proceeding.")
            else:
                raise
    else:
        logger.info(f"Skipping tag creation. Target version is {target_version_name}")

    # AI Summary Pipeline
    ai_summary = ""
    if gemini_api_key and not skip_tag_creation:
        try:
            logger.info("Engaging Gemini AI pipeline for Business Impact summary.")
            genai.configure(api_key=gemini_api_key)
            model = genai.GenerativeModel('gemini-1.5-flash')
            
            diff_text = ""
            if base_tag:
                comp = repo.compare(base_tag.commit.sha, sha)
                for f in comp.files:
                    if not target_dir or f.filename.startswith(target_dir):
                        if f.patch:
                            diff_text += f"\n--- {f.filename} ---\n{f.patch}\n"
            
            # truncate diff_text to ~60000 chars
            if len(diff_text) > 60000:
                diff_text = diff_text[:60000] + "\n...[TRUNCATED]"
                
            commit_messages = "\n".join([f"- {c['description']}" for c in parsed_commits])
            
            prompt = (
                "You are an expert Product Manager. Analyze the following technical commits and code diffs "
                "to write a polished, non-technical 2-paragraph 'Business Impact' summary for our release notes. "
                "Focus on user value, resolved friction points, and architecture enhancements. "
                "Do NOT use markdown headings like '# Release'.\n\n"
                f"Commits:\n{commit_messages}\n\nDiffs:\n{diff_text}"
            )
            
            response = model.generate_content(prompt)
            if response.text:
                ai_summary = "## 🌟 Business Impact\n\n" + response.text.strip() + "\n\n"
        except Exception as e:
            logger.warning(f"AI Generation failed: {e}")

    # Generate Changelog
    features = [c for c in parsed_commits if c['type'] == 'feat']
    fixes = [c for c in parsed_commits if c['type'] == 'fix']
    others = [c for c in parsed_commits if c['type'] not in ['feat', 'fix']]
    
    changelog_lines = [f"# Release {target_version_name}\n"]
    if ai_summary:
        changelog_lines.append(ai_summary)
        
    if features:
        changelog_lines.append("## Features")
        for c in features:
            changelog_lines.append(f"- {c['description']} ({c['sha'][:7]})")
        changelog_lines.append("")
    if fixes:
        changelog_lines.append("## Fixes")
        for c in fixes:
            changelog_lines.append(f"- {c['description']} ({c['sha'][:7]})")
        changelog_lines.append("")
    if others:
        changelog_lines.append("## Other Changes")
        for c in others:
            changelog_lines.append(f"- {c['description']} ({c['sha'][:7]})")
        changelog_lines.append("")
        
    changelog = "\n".join(changelog_lines)
    logger.info("Generated Changelog:\n" + changelog)
    
    # Create Release
    logger.info("Creating GitHub Release")
    release = repo.create_git_release(
        tag=target_version_name,
        name=target_version_name,
        message=changelog,
        draft=False,
        prerelease=False
    )
    
    set_output('new-version', target_version_name)
    set_output('release-url', release.html_url)
    
    # Webhook
    if webhook_url:
        logger.info("Sending webhook notification")
        payload = {"text": f"🚀 **New Release: {target_version_name}**\n\n{changelog}\n\n[View on GitHub]({release.html_url})"}
        resp = requests.post(webhook_url, json=payload)
        if resp.status_code >= 400:
            logger.error(f"Webhook failed: {resp.status_code} - {resp.text}")
        else:
            logger.info("Webhook sent successfully.")

if __name__ == "__main__":
    try:
        main()
    except Exception as e:
        logger.exception("Action failed with an error")
        sys.exit(1)
