SELECT
v_ifce_status_mac.hostname,
v_ifce_status_mac.ifce,
v_ifce_status_mac.description,
v_ifce_status_mac.status,
v_ifce_status_mac.duplex,
v_ifce_status_mac.vlan,
v_ifce_status_mac.speed,
v_ifce_status.type,
v_ifce_status_mac.mac,
macs_to_ips.ip_addr,
cdp_neighbors.remote_switch,
cdp_neighbors.remote_ifce,
cdp_neighbors.remote_sw_type
FROM
v_ifce_status_mac
LEFT OUTER JOIN macs_to_ips ON
v_ifce_status_mac.mac = macs_to_ips.mac_addr
LEFT OUTER JOIN cdp_neighbors ON
v_ifce_status_mac.hostname = cdp_neighbors.hostname and
	v_ifce_status_mac.ifce = cdp_neighbors.local_ifce
