-- events definition
CREATE TABLE jobs (
    id INTEGER NOT NULL,
    user_id INTEGER NOT NULL,
    plugin_id INTEGER NOT NULL,
    config TEXT CHECK (json_valid(config)),
    description TEXT,
    active BOOLEAN,
    PRIMARY KEY (id)
);
CREATE INDEX idx_jobs_user_id ON jobs(user_id);
CREATE INDEX idx_jobs_plugin_id ON jobs(plugin_id);
CREATE TABLE plugins (
    id INTEGER PRIMARY KEY,
    package TEXT NOT NULL UNIQUE,
    interval INTEGER NOT NULL CHECK (interval > 0),
    description TEXT
);