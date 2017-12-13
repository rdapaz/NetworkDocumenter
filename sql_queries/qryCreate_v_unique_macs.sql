DROP VIEW IF EXISTS v_unique_macs;
CREATE VIEW v_unique_macs AS
SELECT
	mac_addresses.hostname,
	mac_addresses.ifce,
	mac_addresses.mac_address,
	mac_addresses.oui_vendor
FROM
	mac_addresses 
GROUP BY
	1,
	2 
HAVING
	count( mac_addresses.mac_address ) = 1;