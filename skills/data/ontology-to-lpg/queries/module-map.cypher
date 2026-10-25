// The module map: one :Module per loaded package (module_tags.py modules) and its requirements; pin is
// the version the package names, target the release loaded. A pin older than the target is a lag.
MATCH (a:Module)-[r:REQUIRES]->(b:Module)
RETURN a.uri AS module, b.uri AS requires, r.pin AS pin, r.pin <> b.uri AS lags
ORDER BY module, requires;
