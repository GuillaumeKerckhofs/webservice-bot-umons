import os
from flask import Flask, request
from github import Github, GithubIntegration

app = Flask(__name__)

app_id = 311883

# Read the bot certificate
with open(
        os.path.normpath(os.path.expanduser('bot_key.pem')),
        'r'
) as cert_file:
    app_key = cert_file.read()
    
# Create an GitHub integration instance
git_integration = GithubIntegration(
    app_id,
    app_key,
)

def issue_opened_event(repo, payload):
    issue = repo.get_issue(number=payload['issue']['number'])
    author = issue.user.login

    
    response = f"Thanks for opening this issue, @{author}! " \
                f"The repository maintainers will look into it ASAP! :speech_balloon:"
    issue.create_comment(f"{response}")
    issue.add_to_labels("Bug")

def pull_request_merged_event(repo, payload):
    pull = repo.get_pull(number=payload['pull_request']['number'])
    author = pull.user.login

    response = f"Thanks @{author}, the pull request has been merged!"

    pull.create_issue_comment(f"{response}")
    repo.get_git_ref(f"heads/{payload['pull_request']['head']['ref']}").delete()

def pull_request_pending_event(repo, payload, old_title = None):
    pull = repo.get_pull(number=payload['pull_request']['number'])
    title = payload['pull_request']['title']

    name = ['WIP', "work in progress", "do not merge"]
    was_wip = old_title and any(n in old_title.lower() for n in name)

    if any(n in title for n in name):
        # set the status to pending
        pull.get_commits().reversed[0].create_status(
            state='pending',
            description='Work in progress',
            context='WIP'
        )
    elif was_wip:
        pull.get_commits().reversed[0].create_status(
            state='success',
            description='Ready for review',
            context='WIP'
        )


def pull_request_edited(repo, payload):
    old_title = None
    if 'title' in payload['changes']:
        old_title = payload['changes']['title']['from']
    pull_request_pending_event(repo, payload, old_title=old_title)
    


def pull_request_opened(repo, payload):
    pull_request_pending_event(repo, payload)



@app.route("/", methods=['POST'])
def bot():
    payload = request.json

    if not 'repository' in payload.keys():
        return "", 204

    owner = payload['repository']['owner']['login']
    repo_name = payload['repository']['name']

    git_connection = Github(
        login_or_token=git_integration.get_access_token(
            git_integration.get_installation(owner, repo_name).id
        ).token
    )
    repo = git_connection.get_repo(f"{owner}/{repo_name}")

    # Check if the event is a GitHub issue creation event
    if all(k in payload.keys() for k in ['action', 'issue']) and payload['action'] == 'opened':
        issue_opened_event(repo, payload)

    # Check if the event is a GitHub merged pull request event
    elif all(k in payload.keys() for k in ['action', 'pull_request']) and payload['action'] == 'closed' and payload['pull_request']['merged']:
        pull_request_merged_event(repo, payload)

    elif all(k in payload.keys() for k in ['action', 'pull_request']) and payload['action'] == 'opened':
        pull_request_opened(repo, payload)

    elif all(k in payload.keys() for k in ['action', 'pull_request']) and payload['action'] == 'edited':
        pull_request_edited(repo, payload)

    return "", 204

if __name__ == "__main__":
    app.run(debug=True, port=5000)
