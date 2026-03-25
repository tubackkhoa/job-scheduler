# Extract numeric job_id from filename, e.g. job-scheduler.job.123 → 123
def extract_job_id(scheduler_id: str) -> int:
    try:
        return int(scheduler_id.split(".")[-1])
    except (ValueError, IndexError):
        raise ValueError(f"Invalid scheduler_id format: {scheduler_id}")
