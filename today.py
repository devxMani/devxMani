"""Regenerates the stats baked into dark_mode.svg / light_mode.svg.

Adapted from ved1beta/ved1beta.

Fine-grained PAT with All Repositories access:
 Account permissions: read:Followers, read:Starring
 Repository permissions: read:Contents, read:Metadata
"""
import datetime
import hashlib
import os
import time

import requests
from dateutil import relativedelta
from lxml import etree

TOKEN = os.environ.get('ACCESS_TOKEN', '').strip()
if not TOKEN:
    raise SystemExit(
        'ACCESS_TOKEN is unset or empty.\n'
        'Add it under Settings > Secrets and variables > Actions > '
        '"Repository secrets" -- a *secret*, not a variable.')

USER_NAME = os.environ.get('USER_NAME', '').strip()
if not USER_NAME:
    raise SystemExit('USER_NAME is unset or empty.')

HEADERS = {'authorization': 'token ' + TOKEN}
COMMENT_SIZE = 7
QUERY_COUNT = {'user_getter': 0, 'follower_getter': 0, 'graph_repos_stars': 0,
               'recursive_loc': 0, 'graph_commits': 0, 'loc_query': 0}

LEN_AGE = 49
LEN_REPO = 6
LEN_CONTRIB = 5
LEN_STAR = 13
LEN_COMMIT = 23
LEN_FOLLOWER = 10
LEN_LOC = 9
LEN_LOC_ADD = 9
LEN_LOC_DEL = 9


def format_plural(unit):
    return 's' if unit != 1 else ''


def account_age(created_at):
    diff = relativedelta.relativedelta(datetime.datetime.today(), created_at)
    return '{} {}, {} {}, {} {}'.format(
        diff.years, 'year' + format_plural(diff.years),
        diff.months, 'month' + format_plural(diff.months),
        diff.days, 'day' + format_plural(diff.days))


def query_count(funct_id):
    QUERY_COUNT[funct_id] += 1


PERM_HINT = (
    'The token authenticated but is not allowed to read this.\n'
    'A fine-grained PAT needs: Repository access = All repositories; '
    'Repository permissions = Contents:read, Metadata:read; '
    'Account permissions = Followers:read, Starring:read.\n'
    'Org-owned repos also require the org to approve the token.'
)

RETRY_STATUS = (502, 503, 504)
RETRY_TRIES = 5


def post_graphql(query, variables):
    delay = 2
    for attempt in range(1, RETRY_TRIES + 1):
        try:
            r = requests.post('https://api.github.com/graphql',
                              json={'query': query, 'variables': variables},
                              headers=HEADERS, timeout=60)
        except requests.exceptions.RequestException as exc:
            if attempt == RETRY_TRIES:
                raise
            print(' network error (%s), retry %d/%d in %ds' % (
                exc.__class__.__name__, attempt, RETRY_TRIES - 1, delay))
            time.sleep(delay)
            delay *= 2
            continue
        if r.status_code in RETRY_STATUS and attempt < RETRY_TRIES:
            print(' HTTP %d, retry %d/%d in %ds' % (
                r.status_code, attempt, RETRY_TRIES - 1, delay))
            time.sleep(delay)
            delay *= 2
            continue
        return r
    return r


FATAL_ERRORS = {'FORBIDDEN', 'INSUFFICIENT_SCOPES', 'UNAUTHORIZED', 'NOT_FOUND'}
_WARNED = set()


def check_graphql(func_name, payload):
    errors = payload.get('errors')
    data = payload.get('data')
    if errors:
        kinds = {e.get("type") for e in errors}
        msgs = '; '.join(e.get('message', '?') for e in errors)
        if data is None or kinds & FATAL_ERRORS:
            hint = '\n' + PERM_HINT if kinds & {'FORBIDDEN', 'INSUFFICIENT_SCOPES'} else ''
            raise Exception('%s: GraphQL errors: %s%s' % (func_name, msgs, hint))
        if msgs not in _WARNED:
            _WARNED.add(msgs)
            print(' note: %s: %s' % (func_name, msgs))
        return payload
    if data is None:
        raise Exception('%s: GraphQL returned no data.\n%s' % (func_name, PERM_HINT))
    return payload


def simple_request(func_name, query, variables):
    r = post_graphql(query, variables)
    if r.status_code == 200:
        check_graphql(func_name, r.json())
        return r
    if r.status_code == 401:
        raise Exception('%s: 401 Unauthorized -- ACCESS_TOKEN is invalid, '
                        'revoked, or expired.' % func_name)
    if r.status_code == 403:
        raise Exception('%s: 403 Forbidden.\n%s\n'
                        '(A 403 partway through a long run instead means the '
                        'undocumented anti-abuse rate limit tripped.)' % (func_name, PERM_HINT))
    raise Exception(func_name, 'has failed with a', r.status_code, r.text, QUERY_COUNT)


def user_getter(username):
    query_count('user_getter')
    query = """
    query($login: String!){
      user(login: $login) { id createdAt }
    }"""
    r = simple_request(user_getter.__name__, query, {'login': username})
    return {'id': r.json()['data']['user']['id']}, r.json()['data']['user']['createdAt']


def follower_getter(username):
    query_count('follower_getter')
    query = """
    query($login: String!){
      user(login: $login) { followers { totalCount } }
    }"""
    r = simple_request(follower_getter.__name__, query, {'login': username})
    return int(r.json()['data']['user']['followers']['totalCount'])


def graph_repos_stars(count_type, owner_affiliation, cursor=None):
    query_count('graph_repos_stars')
    query = """
    query ($owner_affiliation: [RepositoryAffiliation], $login: String!, $cursor: String) {
      user(login: $login) {
        repositories(first: 100, after: $cursor, ownerAffiliations: $owner_affiliation) {
          totalCount
          edges { node { ... on Repository { nameWithOwner stargazers { totalCount } } } }
          pageInfo { endCursor hasNextPage }
        }
      }
    }"""
    variables = {'owner_affiliation': owner_affiliation, 'login': USER_NAME, 'cursor': cursor}
    r = simple_request(graph_repos_stars.__name__, query, variables)
    repos = r.json()['data']['user']['repositories']
    if count_type == 'repos':
        return repos['totalCount']
    if count_type == 'stars':
        return stars_counter(repos['edges'])


def stars_counter(data):
    return sum(node['node']['stargazers']['totalCount'] for node in data)


HISTORY_QUERY = """
    query ($repo_name: String!, $owner: String!, $cursor: String, $author_id: ID!) {
      repository(name: $repo_name, owner: $owner) {
        defaultBranchRef { target { ... on Commit {
          history(first: 50, after: $cursor, author: {id: $author_id}) {
            totalCount
            edges { node { ... on Commit { committedDate }
              author { user { id } } deletions additions } }
            pageInfo { endCursor hasNextPage }
          }
        } } }
      }
    }"""


def recursive_loc(owner, repo_name, data, cache_comment):
    additions = deletions = my_commits = 0
    cursor = None
    while True:
        query_count('recursive_loc')
        r = post_graphql(HISTORY_QUERY,
                         {'repo_name': repo_name, 'owner': owner, 'cursor': cursor,
                          'author_id': OWNER_ID['id']})
        if r.status_code != 200:
            force_close_file(data, cache_comment)
            if r.status_code == 403:
                raise Exception("Too many requests in a short amount of time!\n"
                                "You've hit the non-documented anti-abuse limit!")
            raise Exception('recursive_loc() has failed with a', r.status_code,
                            r.text, QUERY_COUNT)

        payload = r.json()
        try:
            check_graphql('recursive_loc', payload)
        except Exception:
            force_close_file(data, cache_comment)
            raise

        branch = payload['data']['repository']['defaultBranchRef']
        if branch is None:
            return 0, 0, 0
        history = branch['target']['history']

        for edge in history['edges']:
            node = edge['node']
            author = node.get("author") or {}
            if author.get('user') == OWNER_ID:
                my_commits += 1
                additions += node["additions"] or 0
                deletions += node["deletions"] or 0

        if not history['edges'] or not history['pageInfo']['hasNextPage']:
            return additions, deletions, my_commits
        cursor = history['pageInfo']['endCursor']


def loc_query(owner_affiliation, comment_size=0, force_cache=False):
    query = """
    query ($owner_affiliation: [RepositoryAffiliation], $login: String!, $cursor: String) {
      user(login: $login) {
        repositories(first: 60, after: $cursor, ownerAffiliations: $owner_affiliation) {
          edges { node { ... on Repository { nameWithOwner
            defaultBranchRef { target { ... on Commit { history { totalCount } } } } } } }
          pageInfo { endCursor hasNextPage }
        }
      }
    }"""
    edges, cursor = [], None
    while True:
        query_count('loc_query')
        variables = {'owner_affiliation': owner_affiliation, 'login': USER_NAME,
                     'cursor': cursor}
        r = simple_request(loc_query.__name__, query, variables)
        repos = r.json()['data']['user']['repositories']
        edges += repos['edges']
        if not repos['pageInfo']['hasNextPage']:
            return cache_builder(edges, comment_size, force_cache)
        cursor = repos['pageInfo']['endCursor']


def cache_filename():
    return 'cache/' + hashlib.sha256(USER_NAME.encode('utf-8')).hexdigest() + '.txt'


def cache_builder(edges, comment_size, force_cache, loc_add=0, loc_del=0):
    cached = True
    os.makedirs('cache', exist_ok=True)
    filename = cache_filename()
    try:
        with open(filename, 'r') as f:
            data = f.readlines()
    except FileNotFoundError:
        data = ['This line is a comment block. Write whatever you want here.\n'] * comment_size
    with open(filename, 'w') as f:
        f.writelines(data)

    if len(data) - comment_size != len(edges) or force_cache:
        cached = False
        flush_cache(edges, filename, comment_size)
        with open(filename, 'r') as f:
            data = f.readlines()

    cache_comment = data[:comment_size]
    data = data[comment_size:]
    for index in range(len(edges)):
        repo_hash, commit_count, *__ = data[index].split()
        expected = hashlib.sha256(edges[index]['node']['nameWithOwner'].encode('utf-8')).hexdigest()
        if repo_hash == expected:
            try:
                history = edges[index]['node']['defaultBranchRef']['target']['history']
                if int(commit_count) != history['totalCount']:
                    owner, repo_name = edges[index]['node']['nameWithOwner'].split('/')
                    loc = recursive_loc(owner, repo_name, data, cache_comment)
                    data[index] = ("%s %d %d %d %d\n" %
                                   (repo_hash, history["totalCount"], loc[2], loc[0], loc[1]))
            except TypeError:
                data[index] = repo_hash + ' 0 0 0 0\n'
    with open(filename, 'w') as f:
        f.writelines(cache_comment)
        f.writelines(data)
    for line in data:
        loc = line.split()
        loc_add += int(loc[3])
        loc_del += int(loc[4])
    return [loc_add, loc_del, loc_add - loc_del, cached]


def flush_cache(edges, filename, comment_size):
    with open(filename, 'r') as f:
        data = f.readlines()[:comment_size] if comment_size > 0 else []
    with open(filename, 'w') as f:
        f.writelines(data)
        for node in edges:
            f.write(hashlib.sha256(
                node['node']['nameWithOwner'].encode('utf-8')).hexdigest() + ' 0 0 0 0\n')


def force_close_file(data, cache_comment):
    filename = cache_filename()
    with open(filename, 'w') as f:
        f.writelines(cache_comment)
        f.writelines(data)
    print('Partial data saved to', filename)


def commit_counter(comment_size):
    total = 0
    with open(cache_filename(), 'r') as f:
        data = f.readlines()[comment_size:]
    for line in data:
        total += int(line.split()[2])
    return total


def svg_overwrite(filename, age_data, commit_data, star_data, repo_data,
                  contrib_data, follower_data, loc_data):
    tree = etree.parse(filename)
    root = tree.getroot()
    justify_format(root, "age_data", age_data, LEN_AGE)
    justify_format(root, "commit_data", commit_data, LEN_COMMIT)
    justify_format(root, "star_data", star_data, LEN_STAR)
    justify_format(root, "repo_data", repo_data, LEN_REPO)
    justify_format(root, "follower_data", follower_data, LEN_FOLLOWER)
    pad_format(root, "contrib_data", contrib_data, LEN_CONTRIB)
    pad_format(root, "loc_data", loc_data[2], LEN_LOC)
    pad_format(root, "loc_add", loc_data[0], LEN_LOC_ADD)
    pad_format(root, "loc_del", loc_data[1], LEN_LOC_DEL)
    tree.write(filename, encoding='utf-8', xml_declaration=True)


def comma(new_text):
    return '{:,}'.format(new_text) if isinstance(new_text, int) else str(new_text)


def justify_format(root, element_id, new_text, length=0):
    new_text = comma(new_text)
    find_and_replace(root, element_id, new_text)
    just_len = max(0, length - len(new_text))
    if just_len <= 2:
        dot_string = {0: '', 1: ' ', 2: '. '}[just_len]
    else:
        dot_string = ' ' + ('.' * just_len) + ' '
    find_and_replace(root, "%s_dots" % element_id, dot_string)


def pad_format(root, element_id, new_text, length):
    new_text = comma(new_text)
    find_and_replace(root, element_id, new_text)
    find_and_replace(root, "%s_dots" % element_id, " " * max(0, length - len(new_text)))


def find_and_replace(root, element_id, new_text):
    element = root.find(".//*[@id='%s']" % element_id)
    if element is not None:
        element.text = new_text


def perf_counter(funct, *args):
    start = time.perf_counter()
    return funct(*args), time.perf_counter() - start


def formatter(query_type, difference):
    print('%-23s' % (' ' + query_type + ':'), sep='', end='')
    print('%12s' % ('%.4f' % difference + ' s ') if difference > 1
          else '%12s' % ('%.4f' % (difference * 1000) + ' ms'))


if __name__ == '__main__':
    print('Calculation times:')
    user_data, user_time = perf_counter(user_getter, USER_NAME)
    OWNER_ID, acc_date = user_data
    formatter('account data', user_time)

    created = datetime.datetime.strptime(acc_date, '%Y-%m-%dT%H:%M:%SZ')
    age_data, age_time = perf_counter(account_age, created)
    formatter('age calculation', age_time)

    ALL = ['OWNER', 'COLLABORATOR', 'ORGANIZATION_MEMBER']
    total_loc, loc_time = perf_counter(loc_query, ALL, COMMENT_SIZE)
    formatter('LOC (cached)' if total_loc[-1] else 'LOC (no cache)', loc_time)

    commit_data, commit_time = perf_counter(commit_counter, COMMENT_SIZE)
    star_data, star_time = perf_counter(graph_repos_stars, 'stars', ['OWNER'])
    repo_data, repo_time = perf_counter(graph_repos_stars, 'repos', ['OWNER'])
    contrib_data, contrib_time = perf_counter(graph_repos_stars, 'repos', ALL)
    follower_data, follower_time = perf_counter(follower_getter, USER_NAME)

    for index in range(len(total_loc) - 1):
        total_loc[index] = '{:,}'.format(total_loc[index])

    for svg in ('dark_mode.svg', 'light_mode.svg'):
        svg_overwrite(svg, age_data, commit_data, star_data, repo_data,
                      contrib_data, follower_data, total_loc[:-1])

    print('Total GitHub GraphQL API calls:', '%3s' % sum(QUERY_COUNT.values()))
    for funct_name, count in QUERY_COUNT.items():
        print('%-28s %6s' % (' ' + funct_name + ':', count))
