#!/usr/bin/python

import sys, redis, json, re, struct, time, socket, argparse, subprocess

parser = argparse.ArgumentParser(description='Zabbix Redis status script')
parser.add_argument('redis_hostname', nargs='?', default='192.168.0.78')
parser.add_argument('metric', nargs='?')
parser.add_argument('db', default='none', nargs='?')
parser.add_argument('-p', '--port', dest='redis_port', action='store', help='Redis server port', default=6382, type=int)
parser.add_argument('-a', '--auth', dest='redis_pass', action='store', help='Redis server pass', default='ecp@123')
args = parser.parse_args()

zabbix_host = '192.168.0.3'  # Zabbix Server IP
zabbix_port = 10051  # Zabbix Server Port
hostname = '192.168.0.78_6382_REDIS'  # zabbix server UI host'd hostname
# Name of monitored server like it shows in zabbix web ui display
redis_hostname = args.redis_hostname if args.redis_hostname else socket.gethostname()


class Metric(object):
    def __init__(self, host, key, value, clock=None):
        self.host = host
        self.key = key
        self.value = value
        self.clock = clock

    def __repr__(self):
        result = None
        if self.clock is None:
            result = 'Metric(%r, %r, %r)' % (self.host, self.key, self.value)
        else:
            result = 'Metric(%r, %r, %r, %r)' % (self.host, self.key, self.value, self.clock)
        return result


def send_to_zabbix(metrics, zabbix_host='127.0.0.1', zabbix_port=10051):
    result = None
    j = json.dumps
    metrics_data = []
    for m in metrics:
        clock = m.clock or ('%d' % time.time())
        metrics_data.append(
            ('{"host":%s,"key":%s,"value":%s,"clock":%s}') % (j(m.host), j(m.key), j(m.value), j(clock)))
    json_data = ('{"request":"sender data","data":[%s]}') % (','.join(metrics_data))
    data_len = struct.pack('<Q', len(json_data))
    packet = 'ZBXD\x01' + data_len + json_data

    # For debug:
    # print(packet)
    # print(':'.join(x.encode('hex') for x in packet))

    try:
        zabbix = socket.socket()
        zabbix.connect((zabbix_host, zabbix_port))
        zabbix.sendall(packet)
        resp_hdr = _recv_all(zabbix, 13)
        if not resp_hdr.startswith('ZBXD\x01') or len(resp_hdr) != 13:
            print('Wrong zabbix response')
            result = False
        else:
            resp_body_len = struct.unpack('<Q', resp_hdr[5:])[0]
            resp_body = zabbix.recv(resp_body_len)
            zabbix.close()

            resp = json.loads(resp_body)
            # For debug
            # print(resp)
            if resp.get('response') == 'success':
                result = True
            else:
                print('Got error from Zabbix: %s' % resp)
                result = False
    except:
        print('Error while sending data to Zabbix')
        result = False
    finally:
        return result


def _recv_all(sock, count):
    buf = ''
    while len(buf) < count:
        chunk = sock.recv(count - len(buf))
        if not chunk:
            return buf
        buf += chunk
    return buf


def main():
    client = redis.StrictRedis(host=redis_hostname, port=args.redis_port, password=args.redis_pass)
    server_info = client.info()

    a = []
    for i in server_info:
        a.append(Metric(hostname, ('redis[%s]' % i), server_info[i]))

    # Send packet to zabbix
    cmd = "ls /proc/`ps -furedis | grep -v grep  | grep " + str(args.redis_port) + " | grep '[cluster]'|awk '{print $2}'`/fd|wc -l"
    print(cmd)
    sub = subprocess.Popen(cmd, shell=True, stdout=subprocess.PIPE)
    sub.wait()
    FileHandle = sub.stdout.read()
    a.append(Metric(hostname, ('redis[FileHandle]'), FileHandle))
    send_to_zabbix(a, zabbix_host, zabbix_port)


if __name__ == '__main__':
    main()
