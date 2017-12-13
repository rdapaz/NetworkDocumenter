DROP VIEW IF EXISTS v_ifce_status_mac;
CREATE VIEW v_ifce_status_mac AS
SELECT
v_ifce_status.hostname AS hostname,
v_ifce_status.ifce AS ifce,
v_ifce_status.description AS description,
v_ifce_status.status AS status,
v_ifce_status.duplex AS duplex,
v_ifce_status.vlan AS vlan,
v_ifce_status.speed AS speed,
v_ifce_status.type AS type,
v_unique_macs.mac_address AS mac,
v_unique_macs.oui_vendor AS oui_vendor
FROM
v_ifce_status
LEFT OUTER JOIN v_unique_macs ON v_ifce_status.hostname = v_unique_macs.hostname AND v_ifce_status.ifce = v_unique_macs.ifce;