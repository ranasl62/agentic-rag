docker run --rm --gpus all nvidia/cuda:12.2.0-base-ubuntu22.04 nvidia-smi
docker logs -f ollama
docker exec -it ollama nvidia-smi
