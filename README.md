# **Bedrock Prompt Processing API**  

This project provides a FastAPI-based microservice that interacts with AWS Bedrock's Llama3 model to process text generation requests. It uses **Redis** for job queuing and **MongoDB** for storing generated texts. A worker continuously processes queued jobs, ensuring that API rate limits are respected.

---

## **Features**  

- **FastAPI for RESTful API**  
- **Redis Queue for Job Processing**  
- **Rate Limiting** (Prevents exceeding AWS Bedrock API limits)  
- **MongoDB for Storage**  
- **Multi-threaded Worker System**  

---

## **Requirements**  

Ensure you have the following installed before running the service:

- Python 3.8+
- Redis
- MongoDB
- AWS Credentials (for Bedrock API access)

### **Python Dependencies**  

Install the required Python libraries using:

```bash
pip install fastapi redis rq pydantic uvicorn
```

---

## **Project Structure**  

```
/bedrock_api/
│── main.py                      # Main FastAPI app
│── aws/
│   ├── aws_bedrock_connection.py  # AWS Bedrock connection
│── database/
│   ├── mongo_db_connection.py     # MongoDB connection
```

---

## **How It Works**  

1. **Client Sends a Prompt**  
   - A user sends a POST request to `/enqueue` with a text prompt.  
   - The system queues the prompt in Redis and starts a worker if not running.  

2. **Worker Processes the Queue**  
   - The worker retrieves the next job and ensures that it does not exceed API rate limits.  
   - It sends the prompt to AWS Bedrock for text generation.  
   - The generated text is stored in MongoDB.  

3. **Checking Job Status**  
   - The system updates the job's status in Redis after processing.  
   - The user can check job completion by querying Redis.  

---

## **API Endpoints**  

### **1. Enqueue a Prompt**  
- **URL:** `/enqueue`  
- **Method:** `POST`  
- **Payload:**  

```json
{
    "prompt": "Write a story about AI",
    "environment": "UAT"
}
```

- **Response:**  

```json
{
    "success": true,
    "job_id": "b1eaa948-d9d7-4ad6-9e37-31c2b27d0378",
    "message": "Prompt added to queue."
}
```

---

## **Environment Configuration**  

The system supports two environments:  

- **UAT** → Data stored in `SSP-dev` MongoDB database  
- **PROD** → Data stored in `SSP-prod` MongoDB database  

---

## **Worker Execution**  

- The worker runs in a separate thread to process jobs from the queue.
- A Redis lock prevents multiple workers from running simultaneously.

To start the worker manually (if needed):

```python
start_worker(database_name="SSP-dev")  # or "SSP-prod"
```

---

## **Rate Limiting**  

- The system allows up to **3 requests per minute** to AWS Bedrock.  
- If the limit is reached, the job is **requeued** and retried after a delay.  

---

## **Deployment**  

To start the API locally:

```bash
uvicorn main:app --host 0.0.0.0 --port 8000 --reload
```

Make sure **Redis** and **MongoDB** are running before starting the API.

For **Docker Deployment**, create a `Dockerfile` and use:

```bash
docker build -t bedrock-api .
docker run -p 8000:8000 bedrock-api
```

---

## **Future Improvements**  

- Implement a `/status/{job_id}` endpoint to check job progress.
- Currently, this system supports Bedrock Llama 3.3 70B in the us-east-1 region. In the future, it will expand to support multiple models across different AWS regions to enhance flexibility and scalability.

---

## **Contributors**  

- **Saad Shirgaonkar** – Developer  

---

## **License**  

This project is licensed under the MIT License.