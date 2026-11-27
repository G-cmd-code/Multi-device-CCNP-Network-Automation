from netmiko import ConnectHandler


def mgmt_config(hostname, ntp_server="192.168.122.1"):
    return [
        f"hostname {hostname}",
        "banner motd #Authorized access only - CCNP Lab#",
        "logging buffered 16384",
        "no logging console",
        "aaa new-model",
        "aaa authentication login default local",
        "username admin privilege 15 secret cisco",
        f"ntp server {ntp_server}",
        "snmp-server community labRO RO",
    ]

def ospf_config(process_id, networks, passive_ifaces=None, default_originate=False):
    cmds = [f"router ospf {process_id}"]
    for net, wildcard, area in networks:
        cmds.append(f"network {net} {wildcard} area {area}")
    if passive_ifaces:
        for iface in passive_ifaces:
            cmds.append(f"passive-interface {iface}")
    if default_originate:
        cmds.append("default-information originate")
    return cmds

def ospf_interface_auth(interface, key_id, key):
    return [
        f"interface {interface}",
        "ip ospf authentication message-digest",
        f"ip ospf message-digest-key {key_id} md5 {key}",
    ]

def eigrp_config(asn, networks, passive_ifaces=None):
    cmds = [f"router eigrp {asn}", "no auto-summary"]
    for net, wildcard in networks:
        cmds.append(f"network {net} {wildcard}")
    if passive_ifaces:
        for iface in passive_ifaces:
            cmds.append(f"passive-interface {iface}")
    return cmds

def redistribution_config(ospf_pid, eigrp_asn):
    # Run on R2, the boundary router
    return [
        f"router ospf {ospf_pid}",
        f"redistribute eigrp {eigrp_asn} subnets metric-type 1",
        f"router eigrp {eigrp_asn}",
        f"redistribute ospf {ospf_pid} metric 10000 100 255 1 1500",
    ]

def acl_config():
    return [
        "ip access-list standard MGMT_ONLY",
        " permit 192.168.122.0 0.0.0.255",
        " deny any log",
        "ip access-list extended BLOCK_TELNET_FROM_R3",
        " deny tcp 3.3.3.3 0.0.0.0 any eq 23",
        " permit ip any any",
    ]

def apply_acl_to_interface(interface, acl_name, direction="in"):
    return [
        f"interface {interface}",
        f"ip access-group {acl_name} {direction}",
    ]

# ---------- Device definitions ----------

devices = [
    {
        "conn": {"device_type": "cisco_ios_telnet", "host": "192.168.122.10", "username": "admin", "password": "cisco", "secret": "cisco"},
        "name": "R1",
        "config": (
            mgmt_config("R1")
            + ospf_config(1, [("192.168.122.0", "0.0.0.255", 0), ("10.0.12.0", "0.0.0.3", 0), ("1.1.1.1", "0.0.0.0", 0)],
                          passive_ifaces=["Ethernet1/0"], default_originate=True)
            + ospf_interface_auth("Ethernet2/0", 1, "ospfkey123")
            + acl_config()
            + apply_acl_to_interface("Ethernet1/0", "MGMT_ONLY")
        ),
    },
    {
        "conn": {"device_type": "cisco_ios_telnet", "host": "10.0.12.2", "username": "admin", "password": "cisco", "secret": "cisco"},
        "name": "R2",
        "config": (
            mgmt_config("R2")
            + ospf_config(1, [("10.0.12.0", "0.0.0.3", 0), ("2.2.2.2", "0.0.0.0", 0)])
            + ospf_interface_auth("Ethernet1/0", 1, "ospfkey123")
            + eigrp_config(100, [("10.0.23.0", "0.0.0.3"), ("2.2.2.2", "0.0.0.0")])
            + redistribution_config(1, 100)
        ),
    },
    {
        "conn": {"device_type": "cisco_ios_telnet", "host": "3.3.3.3", "username": "admin", "password": "cisco", "secret": "cisco"},
        "name": "R3",
        "config": (
            mgmt_config("R3")
            + eigrp_config(100, [("10.0.23.0", "0.0.0.3"), ("3.3.3.3", "0.0.0.0")])
        ),
    },
]

# ---------- Push configs ----------

for device in devices:
    print(f"\n--- Connecting to {device['name']} ({device['conn']['host']}) ---")
    conn = ConnectHandler(**device["conn"])
    conn.enable()
    output = conn.send_config_set(device["config"])
    print(output)
    conn.set_base_prompt()
    conn.save_config()
    conn.disconnect()
    print(f"--- {device['name']} done ---")