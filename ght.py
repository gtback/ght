#!/usr/bin/env python

import os
import sys

from colorama import init, Fore
import click
import github3
import todoist
import yaml

MAX_TITLE_WORDS = 5
init(autoreset=True)


class Issue:
    """Wrapper around GitHub issue"""

    def __init__(self, issue: github3.issues.ShortIssue):
        self._issue = issue
        org, repo = issue.html_url.split("/")[3:5]
        self.repo = f"{org}/{repo}"
        self.slug = f"{self.repo}#{issue.number}"
        self.url = issue.html_url

        words = issue.title.split()
        if len(words) > MAX_TITLE_WORDS:
            self.title =  " ".join(words[:MAX_TITLE_WORDS]) + "..."
        else:
            self.title = issue.title

    @property
    def markdown_link(self):
        return f"[{self.slug}]({self.url}) - {self.title}"


def parse_note(content):
    res = {}
    lines = content.split("\n")
    # Line 0 should be `"#managed-by-ght"`.
    for line in lines[1:]:
        k, v = line.strip().split("=")
        res[k] = v
    return res


class Todoist:

    def __init__(self, conf):
        self._project_cache = {}
        ttoken = open(".todoist-token").read().strip()
        self.client = todoist.TodoistAPI(ttoken)

        # Label to add to all issues created by this tool
        self.gh = self.get_or_create_label(conf['ght_label'])['id']
        # Label to add to tasks which involve waiting for someone else.
        self.waiting = self.get_or_create_label(conf['waiting_label'])['id']

        self.client.sync()
        self.default_project = self.get_project(conf['default'])
        self.project_mapping = {}
        for k, v in conf['mapping'].items():
            self.project_mapping[k] = self.get_project(v)

        # Cache mapping of GitHub ID to Item ID that represents it.
        self.github_items = self.load_notes()

    def get_project(self, name):
        if name in self._project_cache:
            return self._project_cache[name]
        proj = None
        for project in self.client.state['projects']:
            if project['name'] == name:
                proj = project
        if not proj:
            raise ValueError(f"No Project '{name}'")
        else:
            print(f"Found project '{name}': {proj['id']}")
        self._project_cache[name] = proj
        return proj

    def get_or_create_label(self, name):
        GRAY = 48
        l = None
        for label in self.client.state['labels']:
            if label['name'] == name and not label.data.get("is_deleted") != 0:
                print(f"Found label '{name}': {label['id']}")
                l = label
                break
        if not l:
            l = self.client.labels.add(name, color=GRAY)
            self.client.commit()
            print(f"made label: {l}")
        return l

    def get_managed_item(self, gh_id):
        gh_id = str(gh_id)

        item_id = self.github_items.get(gh_id)

        if item_id is not None:
            # If item has been deleted, this will return None. That's OK.
            return self.client.items.get(item_id)

        return None

    def load_notes(self):
        print("Loading Todoist Note Cache")
        self.client.sync()
        # Mapping of GitHub ID (contained in a note) to item_id that contains that note.
        github_items = {}

        for note in self.client.state["notes"]:
            if note.data.get('is_deleted') == 1:
                continue
            if note['content'].startswith("#managed-by-ght"):
                data = parse_note(note['content'])
                if 'ghid' in data:
                    github_items[data['ghid']] = note['item_id']

        return github_items

    def add_gh_issue_to_todoist(self, issue: Issue):
        t_project = self.project_mapping.get(issue.repo, self.default_project)

        top_item = self.client.items.add(
            issue.markdown_link,
            project_id = t_project['id'],
            labels = [self.gh],
        )
        content = f"#managed-by-ght\nghid={issue._issue.id}"
        self.client.notes.add(top_item['id'], content)

        self.client.items.add("Make PR", parent_id = top_item['id'], labels=[])
        self.client.items.add("Reviewers - Review PR", parent_id = top_item['id'], labels=[self.waiting])
        self.client.items.add("Merge PR", parent_id = top_item['id'], labels=[])
        self.client.items.add("Validate", parent_id = top_item['id'], labels=[])

        self.client.commit()


class GitHub:

    def __init__(self, token):
        self.client = github3.login(token=token)
        self.me = self.client.me()

    @property
    def login(self):
        return self.me.login

    def get_assigned_issues(self):
        return self.client.search_issues(f"is:issue is:open assignee:{self.login}")


def find_github_token():
    # Get GitHub token from environment variable, otherwise fall back to
    # `.ghtoken` config file.
    ghtoken = os.environ.get("GITHUB_TOKEN")
    if not ghtoken:
        try:
            ghtoken = open(".ghtoken").read().strip()
        except:
            print("No GitHub token available. Set GITHUB_TOKEN or create .ghtoken file")
            sys.exit(1)
    return ghtoken


@click.group()
def cli():
    pass


@cli.command()
@click.option("-n", "--dry-run", is_flag=True)
def sync(dry_run):
    conf = yaml.safe_load(open("ght.conf.yaml"))

    ghtoken = find_github_token()
    g = GitHub(ghtoken)

    search_results = g.get_assigned_issues()
    issues = sorted([Issue(sr.issue) for sr in search_results], key=lambda x: x.slug)
    print(f"Found {len(issues)} issues assigned to {g.login}")

    for issue in issues:
        print(f"- {issue.slug} - {issue.title}")
    print()

    t = Todoist(conf)
    print()

    t.client.sync()
    for issue in issues:
        existing_item = t.get_managed_item(issue._issue.id)
        if existing_item:
            print(f"{issue.slug}: Item already exists: https://todoist.com/showTask?id={existing_item['item']['id']}")
        else:
            print(Fore.GREEN + f"{issue.slug}: Creating item")
            if not dry_run:
                t.add_gh_issue_to_todoist(issue)

if __name__ == "__main__":
    cli()
