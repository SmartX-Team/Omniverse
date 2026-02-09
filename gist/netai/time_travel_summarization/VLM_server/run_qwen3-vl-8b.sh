#!/bin/bash
# Run vLLM Qwen3-VL-8B-Instruct container with proper options

docker run -d \
  --name qwen3-vl-8b \
  --gpus '"device=2"' \
  --network host \
  --ipc=host \
  --shm-size=16g \
  -v /home/netai/wonjune/models/Qwen3-VL-8B-Instruct:/models/Qwen3-VL-8B-Instruct:ro \
  vllm/vllm-openai:latest \
    --model /models/Qwen3-VL-8B-Instruct \
    --served-model-name Qwen3-VL-8B-Instruct \
    --tensor-parallel-size 1 \
    --max-model-len 8192 \
    --max-num-seqs 256 \
    --max-num-batched-tokens 8192 \
    --media-io-kwargs '{"video": {"num_frames": -1}}' \
    --host 0.0.0.0 \
    --port 38011
