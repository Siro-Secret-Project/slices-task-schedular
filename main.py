from fastapi import FastAPI
from redis import Redis
from rq import Queue
from pydantic import BaseModel
import uuid
import time
import threading
from aws.aws_bedrock_connection import BedrockLlamaClient
from database.mongo_db_connection import MongoDBDAO
from typing import Literal
from dotenv import load_dotenv
import os

# Load variables from .env into environment
load_dotenv()

# Initialize FastAPI, Redis, and Queue
app = FastAPI()
redis_password = os.getenv("REDIS_PASSWORD")
redis_conn = Redis(host='13.203.74.124', port=6379, password=redis_password)
task_queue = Queue("bedrock_task_queue", connection=redis_conn)

class PromptRequest(BaseModel):
    prompt: str
    environment: Literal["UAT", "PROD"]

RATE_LIMIT_KEY = "bedrock_requests"
MAX_REQUESTS = 99
TIME_WINDOW = 60  # 60 seconds
PROCESSING_LOCK_KEY = "queue_processing_lock"
PROCESSING_TTL = 60  # Lock expiry in seconds

def check_rate_limit():
    """Ensure Bedrock API is not called more than 100 times per minute."""
    current_time = int(time.time())

    # Get last timestamps
    timestamps = redis_conn.lrange(RATE_LIMIT_KEY, 0, -1)
    timestamps = [int(ts) for ts in timestamps if current_time - int(ts) < TIME_WINDOW]

    if len(timestamps) >= MAX_REQUESTS:
        return False  # Rate limit reached

    redis_conn.rpush(RATE_LIMIT_KEY, current_time)  # Store new request timestamp
    redis_conn.ltrim(RATE_LIMIT_KEY, -MAX_REQUESTS, -1)  # Keep only last 100 timestamps
    return True  # Allowed


def generate_text(prompt):
    """Call AWS Bedrock API to generate text."""
    try:
        bedrock_client = BedrockLlamaClient(model_id="us.meta.llama3-3-70b-instruct-v1:0",
                                            region_name="us-east-1")
        generate_text_response = bedrock_client.generate_text_llama(prompt=prompt, max_gen_len=2000)
        if generate_text_response["success"] is False:
            return f"Failed to generate text: {generate_text_response['message']}"
        else:
            return generate_text_response["data"]
    except Exception as e:
        return f"Error: {e}"

def acquire_lock():
    """Try to acquire lock to ensure only one worker runs at a time."""
    return redis_conn.setnx(PROCESSING_LOCK_KEY, 1)

def release_lock():
    """Release the lock once processing is complete."""
    redis_conn.delete(PROCESSING_LOCK_KEY)

def process_queue(database_name: str):
    """Worker function to dequeue prompts and process them."""
    if not acquire_lock():
        print("Worker already running, exiting...")
        return  # Another worker is already running

    try:
        while True:
            job_id = redis_conn.lpop("prompt_queue")
            if not job_id:
                break  # No jobs left, exit gracefully

            job_id = job_id.decode("utf-8")
            prompt = redis_conn.hget(f"job:{job_id}", "prompt").decode("utf-8")

            if not check_rate_limit():
                redis_conn.rpush("prompt_queue", job_id)  # Requeue the job
                time.sleep(5)
                continue

            generated_text = generate_text(prompt)

            # Mongo Client
            mongo_client = MongoDBDAO(database_name=database_name)
            db_document = {
                "job_id": job_id,
                "text": generated_text,
            }
            mongo_client.insert(collection_name="generated_texts", document=db_document)
            redis_conn.hset(f"job:{job_id}", "status", "completed")

            print(f"Processed job {job_id}")

    finally:
        release_lock()  # Ensure lock is released when exiting

def start_worker(database_name: str):
    """Start worker in a separate thread if not already running."""
    threading.Thread(target=process_queue, args=(database_name,), daemon=True).start()

@app.post("/enqueue")
def enqueue_prompt(request: PromptRequest):
    """Enqueue a prompt and start worker if not already running."""
    job_id = str(uuid.uuid4())
    redis_conn.rpush("prompt_queue", job_id)
    redis_conn.hset(f"job:{job_id}", "prompt", request.prompt)
    environment = request.environment
    if environment == "UAT":
        database_name = "SSP-dev"
    elif environment == "PROD":
        database_name = "SSP-prod"
    else:
        database_name = "SSP-dev"
    start_worker(database_name=database_name)  # Ensure worker starts on enqueue

    return {"success": True, "job_id": job_id, "message": "Prompt added to queue."}

