# ght

Track assigned GitHub issues in Todoist

## Setup

`ght` loads a GitHub Personal Access Token from the following locations (stops
after the first one is found):

1. `GITHUB_TOKEN` environment variable
1. `.ghtoken` file in the current working directory.

`ght` loads a Todoist API Token from a `.todoist-token` file in the current
working directory.
