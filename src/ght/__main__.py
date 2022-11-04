#!/usr/bin/env python

# SPDX-FileCopyrightText: 2022 Greg Back <git@gregback.net>
# SPDX-License-Identifier: MIT

import os
import sys

from colorama import init, Fore
import click
import yaml

from ght.github import GitHub, Issue
from ght.todoist import Todoist

init(autoreset=True)


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

    t = Todoist(conf, dry_run)
    print()

    t.client.sync()
    for issue in issues:
        existing_item = t.get_managed_item(issue._issue.id)
        if existing_item:
            print(f"{issue.slug}: Item already exists: https://todoist.com/showTask?id={existing_item['item']['id']}")
        else:
            print(Fore.GREEN + f"{issue.slug}: Creating item")
            t.add_gh_issue_to_todoist(issue)

if __name__ == "__main__":
    cli()
