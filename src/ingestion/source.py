import polars as pl


def fetch_realistic_job_data(last_watermark: str | None) -> tuple[pl.DataFrame, str | None]:
    """
    Simulates fetching messy, real-world data from a Job Board API/Scraper.
    Returns a Polars DataFrame and the new watermark timestamp.
    """
    # Realistic messy payload
    raw_payload = [
        {
            "job_id": 201, 
            "job_title": "Senior Data Engineer", 
            "salary_raw": "$130,000 - $160,000", # Range
            "skills": "Python, Spark, AWS", 
            "location": "New York, NY",
            "ingestion_date": "2024-05-01T10:00:00"
        },
        {
            "job_id": 202, 
            "job_title": "Machine Learning Engineer", 
            "salary_raw": "145000", # Single integer string
            "skills": "Python, PyTorch, Kubernetes", 
            "location": "San Francisco, CA",
            "ingestion_date": "2024-05-01T10:00:00"
        },
        {
            "job_id": 203, 
            "job_title": None, # INVALID: Missing title
            "salary_raw": "$120,000", 
            "skills": "SQL, Tableau", 
            "location": "Austin, TX",
            "ingestion_date": "2024-05-01T10:00:00"
        },
        {
            "job_id": 204, 
            "job_title": "Junior Software Developer", 
            "salary_raw": "Competitive", # INVALID: Unparseable salary
            "skills": "JavaScript, React", 
            "location": "Remote",
            "ingestion_date": "2024-05-01T11:00:00"
        },
        {
            "job_id": 205, 
            "job_title": "Data Analyst", 
            "salary_raw": None, # INVALID: Missing salary entirely
            "skills": "SQL, Excel", 
            "location": "Chicago, IL",
            "ingestion_date": "2024-05-01T11:00:00"
        },
        {
            "job_id": 206, 
            "job_title": "Backend Engineer", 
            "salary_raw": "$90k - $110k", # Messy range with 'k'
            "skills": "Go, Docker, PostgreSQL", 
            "location": "Seattle, WA",
            "ingestion_date": "2024-05-01T12:00:00"
        }
    ]
    
    df = pl.DataFrame(raw_payload)
    
    # INCREMENTAL LOGIC: Filter based on the watermark
    if last_watermark:
        df = df.filter(pl.col("ingestion_date") > last_watermark)
        
    # Calculate the new watermark
    if not df.is_empty():
        new_watermark = df.select(pl.col("ingestion_date").max()).item()
    else:
        new_watermark = last_watermark
        
    return df, new_watermark