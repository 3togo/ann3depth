import argparse
import itertools
import json
import os
import subprocess
import sys


PS_PORT = 5002
WORKER_PORT = 5001

def parse_args():
    parser = argparse.ArgumentParser(
        description='Determines how to distribute tensorflow on the grid jobs.'
    )
    parser.add_argument('--workers', type=int, default=2)
    parser.add_argument('--ps-nodes', type=int, default=2)
    parser.add_argument('hosts', metavar='host', type=str, nargs='+')
    return parser.parse_args()


def convert_memory(value):
    factor = {'b': 1e0, 'k': 1e3, 'm': 1e6, 'g': 1e9}
    try:
        return float(value[:-1]) * factor[value[-1].lower()]
    except ValueError:
        return 0


def parse_info_table(hostlist):
    result = []
    qhost = subprocess.run(' '.join(['qhost', '-F', 'cuda,cuda_cores', '-q',
                            '-h', ','.join(hostlist)]),
                           stdout=subprocess.PIPE, encoding='utf-8',
                           shell=True).stdout.splitlines()
    for line in qhost:
        values = line.split()
        if values[0] in hostlist:
            result.append({
                'host': values[0],
                'cpu': values[2],
                'cuda': 0,
                'cuda_cores': 0,
                'memory': convert_memory(values[4]),
                'memory-human': values[4],
                'queues': []
            })
        elif len(values) == 3 and values[0] == 'Host':
            result[-1]['cuda'] = int(float(values[2].rsplit('=', 1)[-1]))
        elif 'cuda_cores' in values[0]:
            result[-1]['cuda_cores'] = int(float(values[0].rsplit('=', 1)[-1]))
        elif len(values) > 1 and values[1] == 'BIP':
            result[-1]['queues'].append(values[0])
    return result


def remove_invalid_queues(hosts_info):
    allowed_queues = os.environ.get('GRID_QUEUES', '')
    if allowed_queues:
        allowed_queues = set(allowed_queues.split(','))
        hosts_info = [h for h in hosts_info if set(h['queues']) & allowed_queues]

    try:
        with open('.ignore_hosts', 'r') as ihf:
            ignore_hosts = [h for h in ihf.read().splitlines() if h]
    except FileNotFoundError:
        ignore_hosts = []
    for s in ignore_hosts:
        hosts_info = [h for h in hosts_info if s not in h['host']]

    return hosts_info


def split_hosts(hosts, workers, ps):
    hc = hosts.copy()
    if len(hc) < workers + ps:
        print(f'[split_res] Not enough hosts available (got {len(hc)},',
              f'expected {workers + ps})', file=sys.stderr)
        exit(1)

    # Focus on parameter servers: select those first - but on tie, pick lower
    # cuda cores but higher cpu
    hc.sort(key=lambda h: h['cuda'])
    hc.sort(key=lambda h: h['cuda_cores'])
    hc.sort(key=lambda h: h['cpu'], reverse=True)
    hc.sort(key=lambda h: h['memory'], reverse=True)

    # pop first ps many for parameter servers
    ps_list = [hc.pop(0) for i in range(ps)]

    # sort by cuda cores to select best GPU workers, but keep cpu/mem
    hc = [h for h in hc if h['cuda']]
    hc.sort(key=lambda h: h['cuda_cores'], reverse=True)

    return hc[:workers], ps_list


def prepare_output(workers, ps):
    cluster_spec = {'worker': [], 'ps': []}
    for worker, port in zip(workers, itertools.repeat(WORKER_PORT)):
        cluster_spec['worker'].append(f"{worker['host']}:{port}")
    for p, port in zip(ps, itertools.repeat(PS_PORT)):
        cluster_spec['ps'].append(f"{p['host']}:{port}")
    return cluster_spec


def dump_cluster_spec(cluster_spec):
    job_id = os.environ.get('JOB_ID', 'local')
    path = os.path.join('grid_logs', f'cluster_spec.{job_id}')

    with open(path + '.csv', 'w') as cf:
        for k, v in cluster_spec.items():
            for x in v:
                cf.write(f"{x.replace(':', ',')},{k}\n")

    # Clean up before dumping the json
    if not cluster_spec['worker']:
        del cluster_spec['worker']
    if not cluster_spec['ps']:
        del cluster_spec['ps']
    with open(path + '.json', 'w') as jf:
        json.dump(cluster_spec, jf)
    return path


def main():
    args = parse_args()
    print('[split_res] Retreiving host info.', file=sys.stderr)
    hosts_info = parse_info_table(args.hosts)
    print(f'[split_res] Got {len(hosts_info)} hosts.', file=sys.stderr)

    print('[split_res] Filtering queues and hosts.', file=sys.stderr)
    hosts_info = remove_invalid_queues(hosts_info)
    print(f'[split_res] Kept {len(hosts_info)} hosts.', file=sys.stderr)

    print('[split_res] Splitting resources.', file=sys.stderr)
    workers, ps = split_hosts(hosts_info, args.workers, args.ps_nodes)

    print('[split_res] Preparing output.', file=sys.stderr)
    cluster_spec = prepare_output(workers, ps)

    print('[split_res] Storing cluster_spec and printing path.',
          file=sys.stderr)
    return dump_cluster_spec(cluster_spec)


if __name__ == '__main__':
    print(main())
