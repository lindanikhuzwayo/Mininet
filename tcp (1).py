#!/usr/bin/python

# EEE4121F-B Lab 1
# TCP
# Modified from https://github.com/mininet/mininet/wiki/Bufferbloat

from mininet.topo import Topo
from mininet.node import CPULimitedHost
from mininet.link import TCLink
from mininet.net import Mininet
from mininet.log import lg, info
from mininet.util import dumpNodeConnections
from mininet.cli import CLI

from mininet.clean import cleanup 

from subprocess import Popen, PIPE
from time import sleep, time
from multiprocessing import Process
from argparse import ArgumentParser

from monitor import monitor_qlen
import termcolor as T

import sys
import os
import math


# TODO: Don't just read the TODO sections in this code.  Remember that
# one of the goals of this lab is for you to learn how to use
# Mininet. :-)

parser = ArgumentParser(description="TCP tests")
parser.add_argument('--bw-host', '-B',
                    type=float,
                    help="Bandwidth of host links (Mb/s)",
                    default=1000)

parser.add_argument('--bw-net', '-b',
                    type=float,
                    help="Bandwidth of bottleneck (network) link (Mb/s)",
                    required=True)

parser.add_argument('--delay',
                    type=float,
                    help="Link propagation delay (ms)",
                    required=True)

parser.add_argument('--dir', '-d',
                    help="Directory to store outputs",
                    required=True)

parser.add_argument('--time', '-t',
                    help="Duration (sec) to run the experiment",
                    type=int,
                    default=10)

parser.add_argument('--maxq',
                    type=int,
                    help="Max buffer size of network interface in packets",
                    default=100)

# Linux uses CUBIC-TCP by default 
# For the first experiments we want to investigate Reno Behaviour
parser.add_argument('--cong',
                    help="Congestion control algorithm to use",
                    default="reno")

# This  only needs to be changed for the TCP BBR experiments                    
parser.add_argument('--qman',
                    help="Queue management algorithm to use",
                    default="pfifo_fast")


# Expt parameters
args = parser.parse_args()

class TCPTopo(Topo):
    "Simple topology for TCP experiment."

    def build(self, n=2):
        # TODO: create two hosts
        # Here I have created a switch.  If you change its name, its
        # interface names will change from s0-eth1 to newname-eth1.

        # adding two hosts
        h1=self.addHost('h1')
        h2=self.addHost('h2')
        
        #adding switch
        switch = self.addSwitch('s0')
        

         
        # TODO: Add links with appropriate characteristics
        
        self.addLink(h1, s0, bw=args.bw_host, delay=args.delay, max_queue_size=args.maxq)
        self.addLink(h2, s0, bw=args.bw_net, delay=args.delay, max_queue_size=args.maxq)
        
        return

# Simple wrappers around monitoring utilities.  You are welcome to
# contribute neatly written (using classes) monitoring scripts for
# Mininet!
def start_tcpprobe(outfile="cwnd.txt"):
     os.system("rmmod tcp_probe; modprobe tcp_probe full=1;")
     Popen("cat /proc/net/tcpprobe > %s/%s" % (args.dir, outfile),
           shell=True)

def stop_tcpprobe():
    Popen("killall -9 cat", shell=True).wait()

def start_qmon(iface, interval_sec=0.1, outfile="q.txt"):
    monitor = Process(target=monitor_qlen,
                      args=(iface, interval_sec, outfile))
    monitor.start()
    return monitor

def start_iperf(net):
    
    # TODO: Retrieve the hosts, replace with appropriate names
    h2 = net.get('h2')
    h1 = net.get('h1')
    
    
    print("Starting iperf server...")
    # For those who are curious about the -w 16m parameter, it ensures
    # that the TCP flow is not receiver window limited.  If it is,
    # there is a chance that the router buffer may not get filled up.
    server = h1.popen("iperf -s -w 16m")
    # TODO: Start the iperf client on h1 and h2.  Ensure that you create two
    # long lived TCP flows in both directions.
    client = h1.popen("iperf -c {} -t {} > {}/iperf_client.txt".format(h2.IP(), args.time, args.dir), shell=True)
    
def start_webserver(net):
    server = net.get('h1')
    proc = server.popen("python http/webserver.py", shell=True)
    sleep(1)
    return [proc]

def start_ping(net):
    # TODO: Start a ping train from h1 to h2 (or h2 to h1, does it
    # matter?)  Measure RTTs every 0.1 second.  Read the ping man page
    # to see how to do this.

    # Hint: Use host.popen(cmd, shell=True).  If you pass shell=True
    # to popen, you can redirect cmd's output using shell syntax.
    # i.e. ping ... > /path/to/ping.
    h1 = net.get('h1')
    h2 = net.get('h2')
    

    popen = h1.popen("ping -i 0.1 -w {} {} > {}/ping.txt".format(args.time, h2.IP(),args.dir), shell=True)
  

def tcp():
    if not os.path.exists(args.dir):
        os.makedirs(args.dir)
    os.system("sysctl -w net.ipv4.tcp_congestion_control=%s" % args.cong)
    os.system("sysctl -w net.core.default_qdisc=%s" % args.qman)

    cleanup()

    topo = TCPTopo()
    net = Mininet(topo=topo, host=CPULimitedHost, link=TCLink)
    net.start()
    # This dumps the topology and how nodes are interconnected through
    # links.
    dumpNodeConnections(net.hosts)
    # This performs a basic all pairs ping test.
    net.pingAll()

    # Start all the monitoring processes
    #start_tcpprobe("cwnd.txt")
   

    # TODO: Start monitoring the queue sizes.  Since the switch I
    # created is "switch", I monitor one of the interfaces.  Which
    # interface?  The interface numbering starts with 1 and increases.
    # Depending on the order you add links to your network, this
    # number may be 1 or 2.  Ensure you use the correct number.
    qmon = start_qmon(iface='s0-eth2',
                      outfile='%s/q.txt' % (args.dir))

    # TODO: Start iperf, webservers, etc.
    start_iperf(net)
    start_ping(net)
    start_webserver(net)

    # TODO: measure the time it takes to complete webpage transfer
    # from h1 to h2 (say) 3 times.  Hint: check what the following
    # command does: curl -o /dev/null -s -w %{time_total} google.com
    # Now use the curl command to fetch webpage from the webserver you
    # spawned on host h1 (not from google!)

    # Hint: have a separate function to do this and you may find the
    # loop below useful.
    
    start_time, fetch_times = time(), []
    h1, h2 = net.get('h1'), net.get('h2')
    while True:
        # do the measurement (say) 3 times.
        for _ in range(3):
            t = h2.popen("curl -o /dev/null -s -w %{} {}".format("{time_total}", h1.IP())).communicate()[0]
            fetch_times.append(t)
        sleep(5)
        now = time()
        delta = now - start_time
        if delta > args.time:

            break
        print("%.1fs left..." % (args.time - delta))
    
       
    # TODO: compute average (and standard deviation) of the fetch
    # times.  
    
   # fetch_times = map(float, fetch_times)
    #mean = sum(fetch_times) / len(fetch_times)
    #stddev = math.sqrt(sum([(x - mean) ** 2 for x in fetch_times]) / len(fetch_times))
    #print("Mean: {}, Stddev: {}".format(mean, stddev))
    # Hint: The command below invokes a CLI which you can use to
    # debug.  It allows you to run arbitrary commands inside your
    # emulated hosts h1 and h2.
    # CLI(net)

    stop_tcpprobe()
    qmon.terminate()
    net.stop()
    # Ensure that all processes you create within Mininet are killed.
    # Sometimes they require manual killing.
    Popen("pgrep -f webserver.py | xargs kill -9", shell=True).wait()

if __name__ == "__main__":
    tcp()
