FROM vllm/vllm-openai:v0.26.0

WORKDIR /opt/ryuk
COPY workers /opt/ryuk/workers

ENTRYPOINT ["python", "-m", "uvicorn", "workers.vllm.app:app"]
CMD ["--host", "0.0.0.0", "--port", "8000"]
