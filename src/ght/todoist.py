#!/usr/bin/env python

# SPDX-FileCopyrightText: 2022 Greg Back <git@gregback.net>
# SPDX-License-Identifier: MIT

import todoist

from .github import Issue


def parse_note(content):
    res = {}
    lines = content.split("\n")
    # Line 0 should be `"#managed-by-ght"`.
    for line in lines[1:]:
        k, v = line.strip().split("=")
        res[k] = v
    return res


class Todoist:

    def __init__(self, conf, dry_run):

        self.DRY_RUN = dry_run

        self._project_cache = {}
        ttoken = open(".todoist-token").read().strip()
        self.client = todoist.TodoistAPI(ttoken)

        self.template = conf['templates']['_default_']

        self.labels = {}
        for (key, text) in conf["labels"].items():
            self.labels[key] = self.get_or_create_label(text)

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
            if self.DRY_RUN:
                print(f"would create label: {l}")
            else:
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

        project_id = t_project['id'],
        labels = [self.labels['_default_']],
        if not self.DRY_RUN:
            top_item = self.client.items.add(
                issue.markdown_link,
                project_id=project_id,
                labels=labels,
            )
        else:
            print(f"would create item: '{issue.title}' with labels '{labels}'")
            top_item = {'id': "PLACEHOLDER"}

        content = f"#managed-by-ght\nghid={issue._issue.id}"
        if not self.DRY_RUN:
            self.client.notes.add(top_item['id'], content)
        else:
            print(f"would add note: '{content!r}'")

        for child in self.template.get("children", []):
            args = {'parent_id': top_item['id']}
            if isinstance(child, str):
                args['labels'] = []
                content = child
            else:
                args['labels'] = [self.labels[x] for x in child.get('labels', [])]
                content = child['content']

            if not self.DRY_RUN:
                self.client.items.add(content, **args)
            else:
                print(f"would add child: '{content}' with labels '{args['labels']}'")

        if not self.DRY_RUN:
            self.client.commit()
