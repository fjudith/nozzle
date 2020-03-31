#!/usr/bin/env python

import asyncio
import argparse
import json
import logging
import os

from kubernetes import client, config, watch

from nats.aio.client import Client as NATS
from stan.aio.client import Client as STAN
from nats.aio.errors import ErrConnectionClosed, ErrTimeout, ErrNoServers

parser = argparse.ArgumentParser()
parser.add_argument('--in-cluster', help="use in cluster kubernetes config", action="store_true")
parser.add_argument('-l', '--selector', help="Selector (label query) to filter on, supports '=', '==', and '!='.(e.g. -l key1=value1,key2=value2)", default='nozzle=true')
parser.add_argument('-a', '--nats-address', help="address of nats cluster", default=os.environ.get('NATS_ADDRESS', None))
parser.add_argument('-s', '--stan-cluster', help="name of nats streaming cluster", default=os.environ.get('STAN_CLUSTER', None))
parser.add_argument('-d', '--debug', help="enable debug logging", action="store_true")
parser.add_argument('--output-deployments', help="output all deployments to stdout", action="store_true", dest='enable_output')
parser.add_argument('--connect-timeout', help="NATS connect timeout (s)", type=int, default=10, dest='conn_timeout')
parser.add_argument('--max-reconnect-attempts', help="number of times to attempt reconnect", type=int, default=5, dest='conn_attempts')
parser.add_argument('--reconnect-time-wait', help="how long to wait between reconnect attempts", type=int, default=1, dest='conn_wait')
args = parser.parse_args()

logger = logging.getLogger('script')
ch = logging.StreamHandler()
if args.debug:
    logger.setLevel(logging.DEBUG)
    ch.setLevel(logging.DEBUG)
else:
    logger.setLevel(logging.INFO)
    ch.setLevel(logging.INFO)
formatter = logging.Formatter('%(asctime)s - %(name)s - %(levelname)s - %(message)s')
ch.setFormatter(formatter)
logger.addHandler(ch)

if not args.nats_address:
    logger.critical("No NATS cluster specified")
    exit(parser.print_usage())
else:
    logger.debug("Using nats address: %s", args.nats_address)

if args.in_cluster:
    config.load_incluster_config()
else:
    try:
        config.load_kube_config()
    except Exception as e:
        logger.critical("Error creating Kubernetes configuration: %s", e)
        exit(2)

async def run(loop):
    # Use borrowed connection for NATS then mount NATS Streaming
    # client on top.
    nc = NATS()
    
    # Start session with NATS Streaming cluster.
    sc = STAN()

    try:
        await nc.connect(args.nats_address, connect_timeout=args.conn_timeout, max_reconnect_attempts=args.conn_attempts, reconnect_time_wait=args.conn_wait)
        await sc.connect("stan-cluster", "client-123", nats=nc)
    except ErrNoServers as e:
        # Could not connect to any server in the cluster.
        print(e)
        return

    # Synchronous Publisher, does not return until an ack
    # has been received from NATS Streaming.
    await sc.publish("hi", b'hello')
    await sc.publish("hi", b'world')

    total_messages = 0
    future = asyncio.Future(loop=loop)
    async def cb(msg):
        nonlocal future
        nonlocal total_messages
        print("Received a message (seq={}): {}".format(msg.seq, msg.data))
        total_messages += 1
        if total_messages >= 2:
            future.set_result(None)

    # Subscribe to get all messages since beginning.
    sub = await sc.subscribe("hi", start_at='first', cb=cb)
    await asyncio.wait_for(future, 1, loop=loop)

    # Stop receiving messages
    await sub.unsubscribe()

    # Close NATS Streaming session
    await sc.close()

    # We are using a NATS borrowed connection so we need to close manually.
    await nc.close()

if __name__ == '__main__':
    loop = asyncio.get_event_loop()
    try:
        loop.run_until_complete(run(loop))
    except KeyboardInterrupt:
        logger.info('keyboard shutdown')
    finally:
        logger.info('closing event loop')
        loop.close()