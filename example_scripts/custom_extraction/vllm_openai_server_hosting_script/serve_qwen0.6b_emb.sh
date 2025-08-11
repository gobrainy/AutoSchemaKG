export NCCL_P2P_LEVEL=NVL
export CUDA_VISIBLE_DEVICES=3
vllm serve Qwen/Qwen3-Embedding-0.6B \
  --host 0.0.0.0 \
  --port 8128 \
  --gpu-memory-utilization 0.1 \
  --tensor-parallel-size 1 \
  --task embed \
   --max-model-len 8912