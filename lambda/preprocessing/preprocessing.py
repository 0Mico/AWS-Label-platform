import os
import json
import awsutils as aws_ut
from transformers import AutoTokenizer


# Predict how many tokens the text will generate
def _predictTokenCount(tokenizer: AutoTokenizer, text: str):
    estimated_tokens = len(text) // 3  
    return estimated_tokens


# Calculate optimal number of words per chunk to stay under token limit
def _calculateWordsPerChunk(max_tokens: int):
    words_per_chunk = max_tokens // 2   # Estimate 2 tokens per word
    words_per_chunk = int(words_per_chunk * 0.9)  # Add safety margin
    
    return words_per_chunk


# Divides the text in chunks containing a certain number of words
def _chunkTextByWordCount(text: str, words_per_chunk: int):
    words = text.split()
    chunks = []
    
    # Create chunks of specified word count
    for i in range(0, len(words), words_per_chunk):
        chunk_words = words[i:i + words_per_chunk]
        chunk_text = ' '.join(chunk_words)
        chunks.append(chunk_text)
    
    return chunks


def _tokenizeText(tokenizer: AutoTokenizer, text: str, max_tokens: int):
    estimated_tokens = _predictTokenCount(tokenizer, text)
    print(f"Estimated tokens: {estimated_tokens}")
    
    if estimated_tokens <= max_tokens:
        tokens = tokenizer.tokenize(text)
        print(f"Text tokenized directly: {len(tokens)} tokens")
        return tokens
    
    # Text exceeds limit, calculate optimal words per chunk
    words_per_chunk = _calculateWordsPerChunk(max_tokens)
    print(f"Text exceeds {max_tokens} tokens, dividing into chunks of {words_per_chunk} words each")
    
    chunks = _chunkTextByWordCount(text, words_per_chunk)
    print(f"Text divided into {len(chunks)} chunks")
    
    all_tokens = []
    
    for i, chunk in enumerate(chunks):
        chunk_tokens = tokenizer.tokenize(chunk)
        all_tokens.extend(chunk_tokens)
        k
        if len(chunk_tokens) > max_tokens:
            print(f"WARNING: Chunk {i+1} has {len(chunk_tokens)} tokens (exceeds {max_tokens})")
        else:
            print(f"Chunk {i+1}: {len(chunk_tokens)} tokens ({len(chunk.split())} words)")
    
    total_tokens = len(all_tokens)
    print(f"Total tokens after chunking: {total_tokens}")
    
    return all_tokens



def lambda_handler(event, context):
    sns_topic_arn = os.getenv('SNS_TOPIC_ARN')
    sqs_queue_url = aws_ut._retrieveSQSQueueUrl(os.getenv("DEDUPLICATED_JOBS_QUEUE_NAME"))
    tokenizer = AutoTokenizer.from_pretrained("bert-base-multilingual-uncased")
    text_max_tokens = 512

    
    if not sqs_queue_url:
        print("SQS queue URL not found")
        return
    
    try:
        messages = aws_ut._readJobFromSQSQueue(sqs_queue_url)
        if not messages:
            print("No messages in the queue")
            return
        
        for message in messages:
            receipt_handle = message.get('ReceiptHandle')
            job = message.get('Body')
            if not job or not receipt_handle:
                print("Message body or receipt handle is empty")
                continue
            
            try:
                job_data = json.loads(job)
                job_description = job_data.get("Description")
                job_tokenized = _tokenizeText(tokenizer, job_description, text_max_tokens)
                filtered_job = {
                    "Job_ID": job_data.get("Job_ID"),
                    "Title": job_data.get("Title"),
                    "Company": job_data.get("Company_name"),
                    "Description": job_tokenized
                }
                filtered_json_string = json.dumps(filtered_job, ensure_ascii=False)
                
            except json.JSONDecodeError as e:
                print(f"Error decoding JSON: {e}")
                continue

            aws_ut._writeJobToSNSTopic(sns_topic_arn, filtered_json_string)
            
            aws_ut._deleteJobFromSQSQueue(sqs_queue_url, receipt_handle)
            
            print("Message processed and deleted from the queue")

    except Exception as e:
        print(f"Error processing messages from SQS: {e}")
        return