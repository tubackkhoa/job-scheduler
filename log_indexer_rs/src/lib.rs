use pyo3::prelude::*;
use pyo3::types::{PyList, PyDict};
use pyo3::exceptions;
use regex::Regex;
use rusqlite::{params, Connection};
use std::fs::File;
use std::io::{BufRead, BufReader};
use std::path::PathBuf;
use chrono::{Local, NaiveDateTime};
use flate2::read::GzDecoder;

fn iter_log_lines(path: &PathBuf) -> PyResult<Box<dyn Iterator<Item = PyResult<String>>>> {
    let ext = path.extension().and_then(|s| s.to_str()).unwrap_or("");
    if ext == "gz" {
        let f = File::open(path).map_err(|e| exceptions::PyIOError::new_err(e.to_string()))?;
        let decoder = GzDecoder::new(f);
        let reader = BufReader::new(decoder);
        Ok(Box::new(reader.lines().map(|line| {
            line.map_err(|e| exceptions::PyIOError::new_err(e.to_string()))
        })))
    } else {
        let f = File::open(path).map_err(|e| exceptions::PyIOError::new_err(e.to_string()))?;
        let reader = BufReader::new(f);
        Ok(Box::new(reader.lines().map(|line| {
            line.map_err(|e| exceptions::PyIOError::new_err(e.to_string()))
        })))
    }
}


/// Extract job_id from filename like "job-scheduler.job.123"
fn extract_job_id(filename: &str) -> PyResult<i64> {
    let re = Regex::new(r"job-scheduler\.job\.(\d+)").unwrap();
    if let Some(cap) = re.captures(filename) {
        cap.get(1)
            .unwrap()
            .as_str()
            .parse::<i64>()
            .map_err(|_| exceptions::PyValueError::new_err("Invalid job_id format"))
    } else {
        Err(exceptions::PyValueError::new_err(format!(
            "Cannot extract job_id from filename: {}",
            filename
        )))
    }
}

/// LogIndexer Python class
#[pyclass]
struct LogIndexer {
    db: Connection,
    rotate_size: i64,
    log_line_re: Regex,
}

#[pymethods]
impl LogIndexer {
    #[new]
    fn new(db_path: Option<String>, rotate_size: Option<i64>) -> PyResult<Self> {
        let db_path = db_path.unwrap_or_else(|| "logs_index.db".to_string());
        let rotate_size = rotate_size.unwrap_or(100_000);

        // Open SQLite connection
        let db = Connection::open(&db_path)
            .map_err(|e| exceptions::PyIOError::new_err(e.to_string()))?;

        db.execute_batch(
            "PRAGMA journal_mode=WAL;
            PRAGMA synchronous=NORMAL;
            PRAGMA temp_store=MEMORY;
            PRAGMA cache_size=-100000;",
        ).unwrap();

        // Initialize schema
        db.execute_batch(
            "
            CREATE TABLE IF NOT EXISTS logs (
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                job_id INTEGER NOT NULL,
                timestamp TEXT NOT NULL,
                level TEXT NOT NULL,
                message TEXT NOT NULL
            );

            CREATE VIRTUAL TABLE IF NOT EXISTS logs_fts
            USING fts5(
                job_id UNINDEXED,
                level,
                message,
                content='logs',
                content_rowid='id',
                tokenize='unicode61'
            );

            CREATE INDEX IF NOT EXISTS idx_logs_job_id_id
            ON logs(job_id, id DESC);
            "
        ).unwrap();

        let log_line_re = Regex::new(r"^(?P<ts>\d{4}-\d{2}-\d{2}\s+\d{2}:\d{2}:\d{2})\s+\[(?P<level>[A-Z]+)\]\s+(?P<msg>.*)$").unwrap();

        Ok(LogIndexer {
            db,
            rotate_size,
            log_line_re,
        })
    }

    fn rotate_job_logs_by_count(&mut self, job_id: i64, keep: Option<i64>) -> PyResult<()> {
        let keep = keep.unwrap_or(self.rotate_size);
        let tx = self.db.transaction().map_err(|e| exceptions::PyRuntimeError::new_err(e.to_string()))?;
        tx.execute(
            "DELETE FROM logs
             WHERE job_id = ?1
             AND id NOT IN (
                SELECT id FROM logs
                WHERE job_id = ?1
                ORDER BY id DESC
                LIMIT ?2
             )",
            params![job_id, keep],
        ).unwrap();

        // Keep FTS in sync
        tx.execute(
            "DELETE FROM logs_fts WHERE rowid NOT IN (SELECT id FROM logs)",
            [],
        ).unwrap();

        tx.commit().map_err(|e| exceptions::PyRuntimeError::new_err(e.to_string()))?;
        Ok(())
    }

    fn insert_log(&mut self, job_id: i64, level: String, message: String, timestamp: Option<String>) -> PyResult<()> {
        let timestamp = timestamp.unwrap_or_else(|| Local::now().format("%Y-%m-%d %H:%M:%S").to_string());

        let tx = self.db.transaction().map_err(|e| exceptions::PyRuntimeError::new_err(e.to_string()))?;

        tx.execute(
            "INSERT INTO logs (job_id, timestamp, level, message) VALUES (?1, ?2, ?3, ?4)",
            params![job_id, timestamp, level, message],
        ).unwrap();

        let last_id = tx.last_insert_rowid();

        tx.execute(
            "INSERT INTO logs_fts (rowid, job_id, level, message) VALUES (?1, ?2, ?3, ?4)",
            params![last_id, job_id, level, message],
        ).unwrap();

        tx.commit().map_err(|e| exceptions::PyRuntimeError::new_err(e.to_string()))?;

        if last_id % (self.rotate_size as i64 * 3 / 2) == 0 {
            self.rotate_job_logs_by_count(job_id, Some(self.rotate_size))?;
        }
        Ok(())
    }

    fn search_logs(&self, job_id: i64, query: String, limit: Option<usize>, py: Python) -> PyResult<PyObject> {
        let limit = limit.unwrap_or(1000);

        let mut stmt = self.db.prepare(
            "
            SELECT l.job_id, l.timestamp, l.level, l.message
            FROM logs_fts
            JOIN logs l ON l.id = logs_fts.rowid
            WHERE logs_fts.job_id = ?1
            AND logs_fts MATCH ?2
            ORDER BY l.id
            LIMIT ?3
            "
        ).unwrap();

        let rows = stmt.query_map(params![job_id, query, limit as i64], |row| {
            Ok((
                row.get::<_, i64>(0)?,
                row.get::<_, String>(1)?,
                row.get::<_, String>(2)?,
                row.get::<_, String>(3)?,
            ))
        }).unwrap();

        let results = PyList::empty(py);
        for row in rows {
            let (job_id, timestamp, level, message) = row.unwrap();
            let dict = PyDict::new(py);
            dict.set_item("job_id", job_id)?;
            dict.set_item("timestamp", timestamp)?;
            dict.set_item("level", level)?;
            dict.set_item("message", message)?;
            results.append(dict)?;
        }

        Ok(results.to_object(py))
    }

    fn import_log_files(&mut self, filename: String) -> PyResult<()> {
        let path = PathBuf::from(&filename);
        let job_id = extract_job_id(&path.file_name().unwrap().to_string_lossy())?;

        let lines = iter_log_lines(&path)?;

        for line_res in lines {
            let line = line_res?;
            if line.is_empty() {
                continue;
            }
            if let Some(caps) = self.log_line_re.captures(&line) {
                let ts = caps.name("ts").unwrap().as_str().to_string();
                let level = caps.name("level").unwrap().as_str().to_string();
                let msg = caps.name("msg").unwrap().as_str().to_string();

                self.insert_log(job_id, level, msg, Some(ts))?;
            } else {
                // fallback raw line
                self.insert_log(job_id, "INFO".to_string(), line, None)?;
            }
        }
        Ok(())
    }

    fn get_logs_after_id(&self, last_id: Option<i64>, job_id: Option<i64>, limit: Option<usize>, py: Python) -> PyResult<PyObject> {
        let last_id = last_id.unwrap_or(0);
        let limit = limit.unwrap_or(1000);

        let rows = if let Some(job_id) = job_id {
            self.db.prepare(
                "SELECT id, job_id, timestamp, level, message
                 FROM logs
                 WHERE id > ?1 AND job_id = ?2
                 ORDER BY id
                 LIMIT ?3"
            ).unwrap().query_map(params![last_id, job_id, limit as i64], |row| {
                Ok((
                    row.get::<_, i64>(0)?,
                    row.get::<_, i64>(1)?,
                    row.get::<_, String>(2)?,
                    row.get::<_, String>(3)?,
                    row.get::<_, String>(4)?,
                ))
            }).unwrap().collect::<Result<Vec<_>, _>>().unwrap()
        } else {
            self.db.prepare(
                "SELECT id, job_id, timestamp, level, message
                 FROM logs
                 WHERE id > ?1
                 ORDER BY id
                 LIMIT ?2"
            ).unwrap().query_map(params![last_id, limit as i64], |row| {
                Ok((
                    row.get::<_, i64>(0)?,
                    row.get::<_, i64>(1)?,
                    row.get::<_, String>(2)?,
                    row.get::<_, String>(3)?,
                    row.get::<_, String>(4)?,
                ))
            }).unwrap().collect::<Result<Vec<_>, _>>().unwrap()
        };

        let results = PyList::empty(py);
        for (id, job_id, timestamp, level, message) in rows {
            let dict = PyDict::new(py);
            dict.set_item("id", id)?;
            dict.set_item("job_id", job_id)?;
            dict.set_item("timestamp", timestamp)?;
            dict.set_item("level", level)?;
            dict.set_item("message", message)?;
            results.append(dict)?;
        }
        Ok(results.to_object(py))
    }
}

/// PyO3 module
#[pymodule]
fn log_indexer_rs(_py: Python, m: &PyModule) -> PyResult<()> {
    m.add_class::<LogIndexer>()?;
    Ok(())
}
