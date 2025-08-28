import numpy as np
import pandas as pd
from itertools import combinations

# Fat-Tree参数
k_fat = 4
link_rate = 100 # Gbps
link_latency = 1000 # ns
type = "UNIFORM"
oversubscript = 2

# OCS配置参数
MAX_OCS_PORTS = 24  # OCS端口总数上限
PORTS_PER_AGGR = 3  # 每个aggr分配的OCS端口数

# 用户定义的端口映射表
port_pairs = [
    (1, 7), (2, 13), (3, 19), (4, 10), (5, 16), (6, 22),
    (7, 1), (8, 14), (9, 20), (10, 4), (11, 17), (12, 23),
    (13, 2), (14, 8), (15, 21), (16, 5), (17, 11), (18, 24),
    (19, 3), (20, 9), (21, 15), (22, 6), (23, 12), (24, 18)
]

# 验证端口映射表的冲突检查
def validate_port_pairs(port_pairs, max_ports):
    """
    验证用户提供的端口映射表是否有冲突
    """
    # 检查端口是否超出范围
    all_ports = set()
    for p1, p2 in port_pairs:
        if p1 > max_ports or p2 > max_ports or p1 < 1 or p2 < 1:
            raise ValueError(f"端口 ({p1}, {p2}) 超出有效范围 [1, {max_ports}]")
        all_ports.add(p1)
        all_ports.add(p2)
    
    # 检查是否有端口冲突（一个端口连接到多个端口）
    port_connections = {}
    for p1, p2 in port_pairs:
        if p1 in port_connections:
            if port_connections[p1] != p2:
                raise ValueError(f"端口 {p1} 同时连接到端口 {port_connections[p1]} 和 {p2}，存在冲突")
        else:
            port_connections[p1] = p2
    
    print(f"端口映射表验证通过，使用了 {len(all_ports)} 个端口")
    return True

# 验证端口映射表
validate_port_pairs(port_pairs, MAX_OCS_PORTS)

# Fat-Tree拓扑计算（去掉Core节点）
assert(k_fat % 2 == 0)
print("Fat K : {}".format(k_fat))

n_pod = k_fat
print("Number of pods: {}".format(n_pod))

n_agg_per_pod = int(k_fat / 2)
print("Number of Agg per pod: {}, total: {}".format(n_agg_per_pod, n_agg_per_pod * k_fat))

n_tor_per_pod = int(k_fat / 2)
print("Number of ToR per pod: {}, total: {}".format(n_tor_per_pod, n_tor_per_pod * k_fat))

n_server_per_pod = int(k_fat / 2 * k_fat / 2 * oversubscript)
n_server_per_tor = int(k_fat / 2 * oversubscript)
print("Number of servers per ToR: {} (oversubscript:{})".format(n_server_per_tor, oversubscript))
print("Number of servers per pod: {}, total: {}".format(n_server_per_pod, n_server_per_pod * k_fat))

n_server_total = n_server_per_pod * k_fat
n_tor_total = n_tor_per_pod * k_fat
n_agg_total = n_tor_per_pod * k_fat

# 节点ID分配（保持原有编号方式，去掉Core）
i_server = 0
i_tor = n_server_total
i_agg = n_server_total + n_tor_total

# 动态生成aggr_to_ports映射（简化版）
def generate_aggr_to_ports_simple(n_agg_total, ports_per_aggr, max_ports):
    """
    简单顺序分配aggr到OCS端口的映射
    """
    total_ports_needed = n_agg_total * ports_per_aggr
    if total_ports_needed > max_ports:
        raise ValueError(f"需要 {total_ports_needed} 个端口，但最大只有 {max_ports} 个端口")
    
    aggr_to_ports = {}
    port_index = 1  # OCS端口从1开始编号
    
    for aggr_idx in range(n_agg_total):
        aggr_id = i_agg + aggr_idx  # 使用动态生成的aggr ID
        ports = []
        for _ in range(ports_per_aggr):
            ports.append(port_index)
            port_index += 1
        aggr_to_ports[aggr_id] = ports
    
    return aggr_to_ports

# 生成aggr到端口的映射
aggr_to_ports = generate_aggr_to_ports_simple(n_agg_total, PORTS_PER_AGGR, MAX_OCS_PORTS)
print("Aggr to ports mapping:")
for aggr_id, ports in aggr_to_ports.items():
    print(f"  Aggr {aggr_id}: ports {ports}")

# 根据用户提供的端口映射表生成OCS连接矩阵
ocs_matrix = np.zeros((MAX_OCS_PORTS, MAX_OCS_PORTS), dtype=int)
for i, j in port_pairs:
    ocs_matrix[i-1][j-1] = 1

print(f"使用用户提供的 {len(port_pairs)} 个端口连接")

num_link = 0
filename = "ocs_fat_k{}_{}G_{}.txt".format(k_fat, link_rate, type)
with open(filename, "w") as f:
    
    # 服务器到ToR的链路
    for p in range(n_tor_total):
        for i in range(n_server_per_tor):
            id_server = p * n_server_per_tor + i
            id_tor = i_tor + p
            f.write("{} {} {}Gbps {}ns 0.000000\n".format(id_server, id_tor, link_rate, link_latency))
            num_link += 1

    # ToR到Aggr的链路
    for i in range(n_pod):
        for j in range(n_tor_per_pod):
            for l in range(n_agg_per_pod):
                id_tor = i_tor + i * n_tor_per_pod + j
                id_agg = i_agg + i * n_tor_per_pod + l
                f.write("{} {} {}Gbps {}ns 0.000000\n".format(id_tor, id_agg, link_rate, link_latency))
                num_link += 1

    # 生成Aggr之间的OCS链路（通过aggr-ocs端口映射和port_pairs）
    aggr_ids = sorted(aggr_to_ports.keys())
    ocs_links_count = 0
    
    print("建立的Aggr-Aggr OCS连接:")
    # 遍历所有aggr对
    for aggr1, aggr2 in combinations(aggr_ids, 2):
        # 获取两个aggr对应的OCS端口
        ports1 = aggr_to_ports[aggr1]
        ports2 = aggr_to_ports[aggr2]
        
        # 检查这两个aggr的端口是否在port_pairs中有连接
        connection_found = False
        for p1 in ports1:
            for p2 in ports2:
                # 检查端口对(p1,p2)或(p2,p1)是否在port_pairs中
                if (p1, p2) in port_pairs or (p2, p1) in port_pairs:
                    f.write("{} {} {}Gbps {}ns 0.000000\n".format(aggr1, aggr2, link_rate, link_latency))
                    print(f"  {aggr1} -> {aggr2} (通过OCS端口 {p1} -> {p2})")
                    num_link += 1
                    ocs_links_count += 1
                    connection_found = True
                    break
            if connection_found:
                break
    
    print(f"总共建立了 {ocs_links_count} 个Aggr-Aggr OCS连接")

def line_prepender(filename, line):
    with open(filename, "r+") as f:
        content = f.read()
        f.seek(0, 0)
        f.write(line.rstrip('\r\n') + '\n' + content)

# 计算总节点数和交换机数（不包含Core节点）
num_total_node = n_server_total + n_tor_total + n_agg_total
num_total_switch = n_tor_total + n_agg_total
id_switch_all = ""

# 第二行：交换机ID列表（ToR + Aggr，不包含Core）
for i in range(num_total_switch):
    if i == num_total_switch - 1:
        id_switch_all += "{}\n".format(i + n_server_total)
    else:
        id_switch_all += "{} ".format(i + n_server_total)
line_prepender(filename, id_switch_all)

# 第一行：总节点数、交换机数、链路数
line_prepender(filename, "{} {} {}".format(num_total_node, num_total_switch, num_link))

print(f"Generated topology file: {filename}")
print(f"Total nodes: {num_total_node}, Switches: {num_total_switch}, Links: {num_link}")
print(f"节点分布: Servers({n_server_total}), ToRs({n_tor_total}), Aggrs({n_agg_total})")
print(f"链路分布: Server-ToR({n_server_total}), ToR-Aggr({n_tor_total * n_agg_per_pod}), Aggr-Aggr OCS({num_link - n_server_total - n_tor_total * n_agg_per_pod})")

# 生成trace文件
filename_trace = "ocs_fat_k{}_{}G_{}_trace.txt".format(k_fat, link_rate, type)
with open(filename_trace, "w") as f:
    f.write("{}\n".format(n_server_total))
    
    # 服务器ID列表
    server_ids = ""
    for i in range(n_server_total):
        if i == n_server_total - 1:
            server_ids += "{}\n".format(i)
        else:
            server_ids += "{} ".format(i)
    f.write(server_ids)

print(f"Generated trace file: {filename_trace}")