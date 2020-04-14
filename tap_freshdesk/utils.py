import argparse
import collections
import datetime
import functools
import json
import os
import time

DATETIME_FMT = "%Y-%m-%dT%H:%M:%SZ"

def strptime(dt):
    return datetime.datetime.strptime(dt, DATETIME_FMT)


def strftime(dt):
    return dt.strftime(DATETIME_FMT)


class RateLimit(object):
    def __init__(self, limit=1, every=2):
        self.limit = limit
        self.every = every

    def __call__(self, fn):
        times = collections.deque()

        @functools.wraps(fn)
        def wrapper(*args, **kwargs):
            if len(times) >= self.limit:
                t0 = times.pop()
                t = time.time()
                sleep_time = self.every - (t - t0)
                if sleep_time > 0:
                    time.sleep(sleep_time)

            times.appendleft(time.time())
            return fn(*args, **kwargs)
        return wrapper


def chunk(l, n):
    for i in range(0, len(l), n):
        yield l[i:i + n]


def get_abs_path(path):
    return os.path.join(os.path.dirname(os.path.realpath(__file__)), path)


def load_json(path):
    with open(path) as f:
        return json.load(f)


def load_schema(entity):
    return load_json(get_abs_path("schemas/{}.json".format(entity)))


def update_state(state, entity, dt, query_dt=None):
    if dt is None:
        return

    if isinstance(dt, datetime.datetime):
        dt = strftime(dt)
    
    if query_dt:
        if isinstance(query_dt, datetime.datetime):
            query_dt = strftime(query_dt)
        if dt > query_dt:
            dt = query_dt

    if entity not in state:
        state[entity] = dt

    if dt >= state[entity]:
        state[entity] = dt


def parse_args(required_config_keys):
    parser = argparse.ArgumentParser()
    parser.add_argument('-c', '--config', help='Config file', required=True)
    parser.add_argument('-s', '--state', help='State file')
    args = parser.parse_args()

    config = load_json(args.config)
    check_config(config, required_config_keys)

    if args.state:
        state = load_json(args.state)
    else:
        state = {}

    return config, state


def check_config(config, required_keys):
    missing_keys = [key for key in required_keys if key not in config]
    if missing_keys:
        raise Exception("Config is missing required keys: {}".format(missing_keys))
