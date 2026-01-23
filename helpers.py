import re

JOB_ID_RE = re.compile(r"\.([0-9]+)$")

def extract_job_id_int(job_id: str) -> int:
    """Extract numeric job_id from string format (e.g., 'job-scheduler.job.123' -> 123)."""
    m = JOB_ID_RE.search(job_id)
    if m:
        return int(m.group(1))
    # Fallback: try to extract any number from the string
    numbers = re.findall(r"\d+", job_id)
    if numbers:
        return int(numbers[-1])  # Use last number found
    # Last resort: use hash of string (not ideal but works)
    return abs(hash(job_id)) % (10**9)      