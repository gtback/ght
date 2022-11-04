#!/usr/bin/env python

# SPDX-FileCopyrightText: 2022 Greg Back <git@gregback.net>
# SPDX-License-Identifier: MIT

import github3

MAX_TITLE_WORDS = 5

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


class GitHub:

    def __init__(self, token):
        self.client = github3.login(token=token)
        self.me = self.client.me()

    @property
    def login(self):
        return self.me.login

    def get_assigned_issues(self):
        return self.client.search_issues(f"is:issue is:open assignee:{self.login}")
