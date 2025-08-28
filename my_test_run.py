#!/usr/bin/python3
from genericpath import exists
import subprocess
import os
import time
from xmlrpc.client import boolean
import numpy as np
import copy
import shutil
import random
from datetime import datetime
import sys
import os
import argparse
from datetime import date

# randomID
random.seed(datetime.now()) #根据当前时间随机生成ID目录名
MAX_RAND_RANGE = 1000000000

# config template format(...) 将花括号里的占位符替换为实际值
config_template = """TOPOLOGY_FILE config/{topo}.txt
FLOW_FILE config/{flow}.txt

FLOW_INPUT_FILE mix/output/{id}/{id}_in.txt
CNP_OUTPUT_FILE mix/output/{id}/{id}_out_cnp.txt
FCT_OUTPUT_FILE mix/output/{id}/{id}_out_fct.txt
PFC_OUTPUT_FILE mix/output/{id}/{id}_out_pfc.txt
QLEN_MON_FILE mix/output/{id}/{id}_out_qlen.txt

QLEN_MON_START {qlen_mon_start} 
QLEN_MON_END {qlen_mon_end}
SW_MONITORING_INTERVAL {sw_monitoring_interval} 

FLOWGEN_START_TIME {flowgen_start_time} 
FLOWGEN_STOP_TIME {flowgen_stop_time}
BUFFER_SIZE {buffer_size}

CC_MODE {cc_mode}
LB_MODE {lb_mode}
ENABLE_PFC {enabled_pfc}
ENABLE_IRN {enabled_irn}

ALPHA_RESUME_INTERVAL 1
RATE_DECREASE_INTERVAL 4
CLAMP_TARGET_RATE 0
RP_TIMER 300 
FAST_RECOVERY_TIMES 1
EWMA_GAIN {ewma_gain}
RATE_AI {ai}Mb/s
RATE_HAI {hai}Mb/s
MIN_RATE 100Mb/s
DCTCP_RATE_AI {dctcp_ai}Mb/s

ERROR_RATE_PER_LINK 0.0000
L2_CHUNK_SIZE 4000
L2_ACK_INTERVAL 1
L2_BACK_TO_ZERO 0

RATE_BOUND 1
HAS_WIN {has_win}
VAR_WIN {var_win}
FAST_REACT {fast_react}
MI_THRESH {mi}
INT_MULTI {int_multi}
GLOBAL_T 1
U_TARGET 0.95
MULTI_RATE 0
SAMPLE_FEEDBACK 0

ENABLE_QCN 1
USE_DYNAMIC_PFC_THRESHOLD 1
PACKET_PAYLOAD_SIZE 1000

LINK_DOWN 0 0 0 
KMAX_MAP {kmax_map}
KMIN_MAP {kmin_map}
PMAX_MAP {pmax_map}
LOAD {load}
RANDOM_SEED 1
"""


# LB/CC mode matching
cc_modes = {
    "dcqcn": 1,
}

lb_modes = {
    "fecmp": 0,  # ECMP
    "my_fecmp": 10,  # my
}

topo2bdp = {
    "leaf_spine_128_100G_OS2": 104000,  # 2-tier -> all 100Gbps
    "fat_k2_100G_OS2": 156000,  # 3-tier -> all 100Gbps
    "ocs_fat_k2_100G_UNIFORM_OS2": 130000,
}

FLOWGEN_DEFAULT_TIME = 2.0  # see /traffic_gen/traffic_gen.py::base_t


def main():
    # make directory if not exists
    isExist = os.path.exists(os.getcwd() + "/mix/output/")
    if not isExist:
        os.makedirs(os.getcwd() + "/mix/output/")
        print("The new directory is created - {}".format(os.getcwd() + "/mix/output/"))

    parser = argparse.ArgumentParser(description='run simulation')
    parser.add_argument('--cc', dest='cc', action='store',
                        default='dcqcn', help="dcqcn (default: dcqcn)")
    parser.add_argument('--lb', dest='lb', action='store',
                        default='fecmp', help="fecmp (ECMP) (default: fecmp)")
    parser.add_argument('--pfc', dest='pfc', action='store',
                        type=int, default=1, help="enable PFC (default: 1)")
    parser.add_argument('--irn', dest='irn', action='store',
                        type=int, default=0, help="enable IRN (default: 0)")
    parser.add_argument('--simul_time', dest='simul_time', action='store',
                        default='0.01', help="traffic time to simulate (up to 3 seconds) (default: 0.01)")
    parser.add_argument('--buffer', dest="buffer", action='store',
                        default='9', help="the switch buffer size (MB) (default: 9)")
    parser.add_argument('--netload', dest='netload', action='store', type=int,
                        default=40, help="Network load at NIC to generate traffic (default: 40.0)")
    parser.add_argument('--bw', dest="bw", action='store',
                        default='100', help="the NIC bandwidth (Gbps) (default: 100)")
    parser.add_argument('--topo', dest='topo', action='store',
                        default='fat_k2_100G_OS2', help="the name of the topology file (default: fat_k2_100G_OS2)")
    parser.add_argument('--cdf', dest='cdf', action='store',
                        default='Solar2022', help="the name of the cdf file (default: Solar2022)")
    parser.add_argument('--enforce_win', dest='enforce_win', action='store',
                        type=int, default=0, help="enforce to use window scheme (default: 0)")
    parser.add_argument('--sw_monitoring_interval', dest='sw_monitoring_interval', action='store',
                        type=int, default=10000, help="interval of sampling statistics for queue status (default: 10000ns)")

    args = parser.parse_args()

    # make running ID of this config
    # need to check directory exists or not
    isExist = True
    config_ID = 0
    while (isExist):
        config_ID = str(random.randrange(MAX_RAND_RANGE))
        isExist = os.path.exists(os.getcwd() + "/mix/output/" + config_ID)

    # input parameters
    cc_mode = cc_modes[args.cc]
    lb_mode = lb_modes[args.lb]
    enabled_pfc = int(args.pfc)
    enabled_irn = int(args.irn)
    bw = int(args.bw)
    buffer = args.buffer
    topo = args.topo
    enforce_win = args.enforce_win # 是否强制窗口，DCQCN是基于速率的，没有窗口
    cdf = args.cdf
    flowgen_start_time = FLOWGEN_DEFAULT_TIME  # default: 2.0
    flowgen_stop_time = flowgen_start_time + \
        float(args.simul_time)  # default: 2.0
    sw_monitoring_interval = int(args.sw_monitoring_interval)

    # get over-subscription ratio from topoogy name
    netload = args.netload
    oversub = int(topo.replace("\n", "").split("OS")[-1].replace(".txt", ""))
    assert (int(args.netload) % oversub == 0)
    hostload = int(args.netload) / oversub
    assert (hostload > 0)

    # Sanity checks
    if float(args.simul_time) < 0.005:
        raise Exception("CONFIG ERROR : Runtime must be larger than 5ms (= warmup interval).")

    # sniff number of servers
    with open("config/{topo}.txt".format(topo=args.topo), 'r') as f_topo:
        line = f_topo.readline().split(" ") # 读取拓扑文件首行，提取主机与链路数量
        n_host = int(line[0]) - int(line[1]) #节点总数-交换机数量 = 主机数量

    assert (hostload >= 0 and hostload < 100)
    flow = "L_{load:.2f}_CDF_{cdf}_N_{n_host}_T_{time}ms_B_{bw}_flow".format(
        load=hostload, cdf=args.cdf, n_host=n_host, time=int(float(args.simul_time)*1000), bw=bw) # 构造流量文件名：负载、流量分布、主机数时长等信息

    # check the file exists
    if (exists(os.getcwd() + "/config/" + flow + ".txt")):
        print("Input traffic file with load:{load:.2f}, cdf:{cdf}, n_host:{n_host} already exists".format(
            load=hostload, cdf=cdf, n_host=n_host))
    else:  # make the input traffic file
        print("Generate a input traffic file...")
        print("python ./traffic_gen/traffic_gen.py -c {cdf} -n {n_host} -l {load} -b {bw} -t {time} -o {output}".format(
            cdf=os.getcwd() + "/traffic_gen/" + args.cdf + ".txt",
            n_host=n_host,
            load=hostload / 100.0,
            bw=args.bw + "G",
            time=args.simul_time,
            output=os.getcwd() + "/config/" + flow + ".txt"))

        os.system("python ./traffic_gen/traffic_gen.py -c {cdf} -n {n_host} -l {load} -b {bw} -t {time} -o {output}".format(
            cdf=os.getcwd() + "/traffic_gen/" + args.cdf + ".txt",
            n_host=n_host,
            load=hostload / 100.0,
            bw=args.bw + "G",
            time=args.simul_time,
            output=os.getcwd() + "/config/" + flow + ".txt")) 

    # sanity check - bandwidth
    with open("config/{topo}.txt".format(topo=args.topo), 'r') as f_topo:
        first_line = f_topo.readline().split(" ")
        n_host = int(first_line[0]) - int(first_line[1])
        n_link = int(first_line[2])
        i = 0
        for line in f_topo.readlines()[1:]:
            i += 1
            if (i > n_link):
                break
            parsed = line.split(" ")
            if len(parsed) > 2 and (int(parsed[0]) < n_host or int(parsed[1]) < n_host):
                assert (int(parsed[2].replace("Gbps", "")) == int(bw))
    print("All NIC bandwidth is {bw}Gbps".format(bw=bw))

    # make directory if not exists
    isExist = os.path.exists(os.getcwd() + "/mix/output/" + config_ID + "/")
    assert (not isExist)
    os.makedirs(os.getcwd() + "/mix/output/" + config_ID + "/")
    print("The new directory is created  - {}".format(os.getcwd() +
          "/mix/output/" + config_ID + "/"))

    config_name = os.getcwd() + "/mix/output/" + config_ID + "/config.txt"
    print("Config filename:{}".format(config_name))

    # By default, DCQCN uses no window (rate-based).
    has_win = 0
    var_win = 0
    if (enforce_win == 1):  # enforcement
        has_win = 1
        var_win = 1
        if enforce_win == 1:
            print("### INFO: Enforced to use window scheme! ###")

    # record to history
    simulday = datetime.now().strftime("%m/%d/%y")
    with open("./mix/.history", "a") as history:
        history.write("{simulday},{config_ID},{cc_mode},{lb_mode},{pfc},{irn},{has_win},{var_win},{topo},{bw},{cdf},{load},{time}\n".format(
            simulday=simulday,
            config_ID=config_ID,
            cc_mode=cc_mode,
            lb_mode=lb_mode,
            pfc=enabled_pfc,
            irn=enabled_irn,
            has_win=has_win,
            var_win=var_win,
            topo=topo,
            bw=bw,
            cdf=cdf,
            load=netload,
            time=args.simul_time,
        ))

    # 1 BDP calculation
    if topo2bdp.get(topo) == None:
        print("ERROR - topology is not registered in run.py!!", flush=True)
        return
    bdp = int(topo2bdp[topo])
    print("1BDP = {}".format(bdp))

    # DCQCN parameters
    kmax_map = "6 %d %d %d %d %d %d %d %d %d %d %d %d" % (
        bw*200000000, 400, bw*500000000, 400, bw*1000000000, 400, bw*2*1000000000, 400, bw*2500000000, 400, bw*4*1000000000, 400)
    kmin_map = "6 %d %d %d %d %d %d %d %d %d %d %d %d" % (
        bw*200000000, 100, bw*500000000, 100, bw*1000000000, 100, bw*2*1000000000, 100, bw*2500000000, 100, bw*4*1000000000, 100)
    pmax_map = "6 %d %d %d %d %d %.2f %d %.2f %d %.2f %d %.2f" % (
        bw*200000000, 0.2, bw*500000000, 0.2, bw*1000000000, 0.2, bw*2*1000000000, 0.2, bw*2500000000, 0.2, bw*4*1000000000, 0.2)
    #根据带宽bw构建DCQCN的阈值映射：每个“阈值(单位随实现) + 常数/概率”成对出现；开头的“6”表示有6段
    # queue monitoring
    qlen_mon_start = flowgen_start_time
    qlen_mon_end = flowgen_stop_time

    # DCQCN parameters
    ai = 10 * bw / 25   # Additive Increase步长
    hai = 25 * bw / 25  # Hight-rate AI步长
    dctcp_ai = 1000
    fast_react = 0
    mi = 0              # 乘法减小阈值（若适用）。
    int_multi = 1
    ewma_gain = 0.00390625

    config = config_template.format(id=config_ID, topo=topo, flow=flow,
                                    qlen_mon_start=qlen_mon_start, qlen_mon_end=qlen_mon_end, flowgen_start_time=flowgen_start_time,
                                    flowgen_stop_time=flowgen_stop_time, sw_monitoring_interval=sw_monitoring_interval,
                                    load=netload, buffer_size=buffer, lb_mode=lb_mode,
                                    enabled_pfc=enabled_pfc, enabled_irn=enabled_irn,
                                    cc_mode=cc_mode,
                                    ai=ai, hai=hai, dctcp_ai=dctcp_ai,
                                    has_win=has_win, var_win=var_win,
                                    fast_react=fast_react, mi=mi, int_multi=int_multi, ewma_gain=ewma_gain,
                                    kmax_map=kmax_map, kmin_map=kmin_map, pmax_map=pmax_map)

    with open(config_name, "w") as file:
        file.write(config)
    #记录配置
    
    # run program
    print("Running simulation...")
    output_log = config_name.replace(".txt", ".log")
    run_command = "./waf --run 'scratch/ecmp_test {config_name}' > {output_log} 2>&1".format(
        config_name=config_name, output_log=output_log)
    with open("./mix/.history", "a") as history:
        history.write(run_command + "\n")
        history.write(
            "./waf --run 'scratch/ecmp_test' --command-template='gdb --args %s {config_name}'\n".format(
                config_name=config_name)
        )
        history.write("\n")

    print(run_command)
    os.system("./waf --run 'scratch/ecmp_test {config_name}' > {output_log} 2>&1".format(
        config_name=config_name, output_log=output_log))

    ####################################################
    #                 Analyze the output FCT           #
    ####################################################
    # NOTE: collect data except warm-up and cold-finish period
    fct_analysis_time_limit_begin = int(
        flowgen_start_time * 1e9) + int(0.005 * 1e9)  # warmup
    fct_analysistime_limit_end = int(
        flowgen_stop_time * 1e9) + int(0.05 * 1e9)  # extra term

    # 调用FCT处理脚本
    print("Analyzing output FCT...")
    print("python3 fctAnalysis.py -id {config_ID} -dir {dir} -bdp {bdp} -sT {fct_analysis_time_limit_begin} -fT {fct_analysistime_limit_end} > /dev/null 2>&1".format(
        config_ID=config_ID, dir=os.getcwd(), bdp=bdp, fct_analysis_time_limit_begin=fct_analysis_time_limit_begin, fct_analysistime_limit_end=fct_analysistime_limit_end))
    os.system("python3 fctAnalysis.py -id {config_ID} -dir {dir} -bdp {bdp} -sT {fct_analysis_time_limit_begin} -fT {fct_analysistime_limit_end} > /dev/null 2>&1".format(
        config_ID=config_ID, dir=os.getcwd(), bdp=bdp, fct_analysis_time_limit_begin=fct_analysis_time_limit_begin, fct_analysistime_limit_end=fct_analysistime_limit_end))

    print("\n\n============== Done ============== ")


if __name__ == "__main__":
    main()