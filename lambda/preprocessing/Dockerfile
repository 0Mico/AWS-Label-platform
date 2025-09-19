FROM public.ecr.aws/lambda/python:3.12

WORKDIR ${LAMBDA_TASK_ROOT}

ENV HF_HOME=/tmp/huggingface

COPY requirements.txt .

RUN pip install --no-cache-dir --upgrade pip && \
    pip install --no-cache-dir -r requirements.txt

COPY preprocessing.py .
COPY awsutils.py .

# Pre-download tokenizer model because during execution the function cannot download it:
# the container file system is read-only except for /tmp.
RUN python -c "from transformers import AutoTokenizer; AutoTokenizer.from_pretrained('bert-base-multilingual-uncased', cache_dir='/tmp/transformers')"

CMD ["preprocessing.lambda_handler"]