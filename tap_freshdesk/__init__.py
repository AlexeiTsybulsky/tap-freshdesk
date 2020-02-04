#!/usr/bin/env python3

import sys
import time
from datetime import datetime, timedelta
import backoff
import requests
from requests.exceptions import HTTPError
import singer

from tap_freshdesk import utils


REQUIRED_CONFIG_KEYS = ['api_key', 'domain']
PER_PAGE = 100
BASE_URL = "https://{}.freshdesk.com"
CONFIG = {}
STATE = {}

endpoints = {
    "ticket_activities": "/api/v2/export/ticket_activities",
}

logger = singer.get_logger()
session = requests.Session()


def get_url(endpoint, **kwargs):
    return BASE_URL.format(CONFIG['domain']) + endpoints[endpoint].format(**kwargs)

@backoff.on_exception(backoff.expo,
                      (requests.exceptions.RequestException),
                      max_tries=5,
                      giveup=lambda e: e.response is not None and 400 <= e.response.status_code < 500,
                      factor=2)
@utils.ratelimit(1, 2)
def request(url, params=None, auth=None):
    params = params or {}
    auth = auth or None
    headers = {"Content-Type": "application/json"}
    if 'user_agent' in CONFIG:
        headers['User-Agent'] = CONFIG['user_agent']

    req = requests.Request('GET', url, params=params, auth=auth, headers=headers).prepare()
    logger.info("GET {}".format(req.url))
    resp = session.send(req)

    if 'Retry-After' in resp.headers:
        retry_after = int(resp.headers['Retry-After'])
        logger.info("Rate limit reached. Sleeping for {} seconds".format(retry_after))
        time.sleep(retry_after)
        return request(url, params, auth)

    resp.raise_for_status()

    return resp

def get_date(entity):
    if entity not in STATE:
        STATE[entity] = (datetime.now() - timedelta(1)).strftime('%Y-%m-%d')

    return STATE[entity]


def sync_ticket_activities():
    logger.info("Getting ticket_activities URL")

    auth = (CONFIG['api_key'], "")

    endpoint = "ticket_activities"

    activities_date = get_date(endpoint)

    params = {
        'created_at': activities_date
    }

    data = request(get_url(endpoint), params, auth).json()

    export_url = data['export'][0]['url']
    data = request(export_url).json()

    updated_schema = {
        "properties": {}
    }

    for row in data['activities_data']:
        for key in row['activity'].keys():
            if key not in ['note', 'automation', 'association', 'requester_id', 'source', 'priority', 'new_ticket', 'agent_id','added_tags','removed_tags','added_watcher','removed_watcher','Updated Amendment Tool in Internal Tools','send_email','thank_you_note','spam','deleted']:
                updated_schema['properties'][key] = { "type": ["null", "string"] }
        row['performed_at'] = datetime.strftime(datetime.strptime(row['performed_at'], '%d-%m-%Y %H:%M:%S %z'), '%Y-%m-%dT%H:%M:%SZ')

    bookmark_property = 'performed_at'
    schema = utils.load_schema('ticket_activities')
    schema['properties']['activity']['properties'].update(updated_schema['properties'])

    singer.write_schema('ticket_activities',
                    schema,
                    [],
                    bookmark_properties=[bookmark_property])

    for row in data['activities_data']:
        logger.info("Ticket {}: Syncing".format(row['ticket_id']))

        utils.update_state(STATE, "ticket_activities", row[bookmark_property])
        singer.write_record('ticket_activities', row, time_extracted=singer.utils.now())

    singer.write_state(STATE)

def do_sync():
    logger.info("Starting FreshDesk sync")

    try:
        sync_ticket_activities()
    except HTTPError as e:
        logger.critical(
            "Error making request to Freshdesk API: GET %s: [%s - %s]",
            e.request.url, e.response.status_code, e.response.content)
        sys.exit(1)

    logger.info("Completed sync")


def main_impl():
    config, state = utils.parse_args(REQUIRED_CONFIG_KEYS)
    CONFIG.update(config)
    STATE.update(state)
    do_sync()


def main():
    try:
        main_impl()
    except Exception as exc:
        logger.critical(exc)
        raise exc


if __name__ == '__main__':
    main()