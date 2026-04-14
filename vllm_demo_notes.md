# vLLM Demo Notes

## 1) What is vLLM?

vLLM is a high-throughput LLM inference and serving engine designed to make large language models much more efficient in production.

It can run as an OpenAI-compatible HTTP server, so applications can call it like they call the OpenAI API, but you host the model yourself.

vLLM is positioned as a serving system with features like:

- efficient KV-cache management
- continuous batching
- chunked prefill
- prefix caching
- Prometheus metrics via `/metrics`

### Why people use vLLM

People use vLLM because raw Hugging Face generation is usually not enough for production.

In production, you care about:

- many users hitting the model at once
- latency
- throughput
- memory fragmentation
- repeated prompts
- observability
- compatibility with existing clients

vLLM exists to solve those serving problems.

It is not just “run a model.” It is “run a model efficiently as a service.”

---

## 2) Core concepts behind vLLM

### 2.1 OpenAI-compatible server

vLLM can expose models through an HTTP server that supports OpenAI-style endpoints like chat completions and completions.

That is why the demo was built as:

- a server using `vllm serve ...`
- a client benchmark script sending requests over HTTP

**Real-world use case**

This is how you build:

- internal enterprise chatbots
- coding assistants
- support assistants
- RAG services
- agent backends

without changing all of your client code.

---

### 2.2 Continuous batching

Continuous batching means the server does not behave like a naive queue where one big request blocks everything else.

Instead, vLLM keeps the GPU busy by dynamically mixing active requests and scheduling work across iterations.

This is one of the main reasons it is useful for multi-user serving.

### Why it matters

In a real chatbot system, users do not arrive at the exact same millisecond.

Continuous batching lets the system absorb staggered arrivals efficiently.

**Real-world use case**

- customer support bots
- internal copilots
- coding assistants
- voice assistants

where many users make short requests concurrently.

---

### 2.3 Prefill vs decode

LLM inference has two different phases:

- **Prefill**: process the input prompt and build the KV cache
- **Decode**: generate one token at a time using that KV cache

These two phases stress the system differently, and modern serving systems optimize around that.

**Real-world use case**

- long-document QA
- meeting summarization
- code review on long files
- RAG prompts with large retrieved contexts

---

### 2.4 Chunked prefill

In vLLM V1, chunked prefill is enabled by default whenever possible.

With chunked prefill enabled, the scheduler prioritizes decode requests first, then uses remaining `max_num_batched_tokens` budget for prefills. If a prefill does not fit, it is chunked automatically.

### Why it matters

A single huge prompt should not freeze an interactive system.

**Real-world use case**

You upload a big policy document to a legal assistant while other users are asking small chat questions.

Chunked prefill helps the server stay responsive.

---

### 2.5 Prefix caching

Automatic Prefix Caching stores KV cache for previously seen prompt prefixes so that future requests with the same prefix can skip recomputing that shared part.

### Why it matters

Many production systems reuse the same long system prompt, tools description, policy prompt, or agent instructions across requests.

**Real-world use case**

- agentic systems
- enterprise copilots
- structured support bots
- coding assistants with fixed guardrails
- RAG systems with repeated templates

---

### 2.6 Metrics and observability

vLLM exposes Prometheus-compatible metrics at `/metrics`.

### Why it matters

A production AI service is not useful if you cannot measure:

- latency
- throughput
- queueing
- request counts
- cache behavior
- server health

**Real-world use case**

- SRE-style monitoring for AI platforms
- Grafana dashboards
- autoscaling decisions
- regression detection after model or config changes

---

## 3) Why we chose a server + client benchmark design

We did not want just “run a model once.”

We wanted to demonstrate serving mechanics.

So the right architecture was:

- vLLM server as the serving engine
- async Python client to simulate load
- results logging
- plots and metrics

That mirrors real serving:

- frontend/app sends requests
- model server handles them
- metrics are collected
- performance is analyzed

This is also why using the OpenAI-compatible server was a good choice: it makes the demo realistic and production-like.

---

## 4) Why we picked smaller models

We initially discussed larger models, but the setup was on a shared Kubeflow GPU.

So the serving problem was not “best answer quality,” it was “stable startup with enough KV cache.”

We moved from 3B-class thinking toward lighter choices, and finally used:

- `Qwen/Qwen2.5-1.5B-Instruct`

as the practical compromise.

### Why that was a good choice

A smaller model leaves more GPU memory available for:

- KV cache
- batching
- multiple requests
- easier startup on a shared device

**Real-world use case**

For a teaching demo or prototype platform, a smaller but stable model is often better than a bigger unstable model.

---

## 5) Real-world mapping of each concept

### vLLM itself

**Use case**

- enterprise-hosted chat service
- coding copilot
- internal assistant
- document Q&A backend

**Why**

- OpenAI-compatible API
- high throughput
- observability

---

### Continuous batching

**Use case**

Many short chat requests from many users.

**Why**

Better GPU utilization and lower latency under concurrency.

---

### Chunked prefill

**Use case**

- long-context RAG
- legal docs
- meeting transcripts
- long code files

**Why**

A giant prompt should not destroy interactivity for everyone else.

---

### Prefix caching

**Use case**

- agentic systems
- repeated system prompts
- repetitive enterprise prompt templates

**Why**

Skip recomputing the shared prompt prefix and improve TTFT.

---

## 6) Other inference server options

There are several solid alternatives to vLLM, and the “best” one depends on what you want to optimize for:

- raw NVIDIA performance
- easiest local setup
- Kubernetes-native operations
- programmable distributed serving

### 6.1 Text Generation Inference (TGI)

TGI from Hugging Face is the closest mainstream alternative to vLLM.

It is a strong choice if you want a mature server focused specifically on transformer text generation.

**Highlights**

- tensor parallelism
- token streaming
- continuous batching
- Prometheus / OpenTelemetry observability
- optimized inference with Flash Attention and Paged Attention

---

### 6.2 TensorRT-LLM + Triton Inference Server

This is the enterprise / HPC-style path when you are fully committed to NVIDIA GPUs.

TensorRT-LLM is used for optimized LLM execution, while Triton is the broader inference server that can serve models from multiple frameworks.

**Best when**

- you want maximum performance on NVIDIA infrastructure
- you are comfortable with a more complex deployment stack

---

### 6.3 SGLang

SGLang is a strong research-oriented serving alternative.

**Highlights**

- RadixAttention for prefix caching
- prefill-decode disaggregation
- speculative decoding
- continuous batching
- paged attention
- chunked prefill
- multi-LoRA batching
- multiple parallelism strategies

**Best when**

You want to explore advanced serving ideas beyond a basic demo.

---

### 6.4 Ollama

Ollama is one of the easiest options for local developer setup.

It exposes a local API and is great for simple model execution and integration.

**Best when**

- you want very quick local experimentation
- you care more about simplicity than deep serving-system benchmarking

---

### 6.5 llama.cpp / llama-cpp-python server

This is a practical option for lightweight CPU / edge / GGUF-style serving.

**Best when**

- you want a lightweight OpenAI-compatible server
- you want quantized local models
- you need laptop or edge deployment

---

### 6.6 KServe

Since the environment already uses Kubeflow, KServe is a very important option.

KServe is a Kubernetes-native serving platform for predictive and generative AI.

**Best when**

- you want production-style Kubernetes deployment
- you want autoscaling and rollout control
- you want to run vLLM or Hugging Face runtimes inside a managed serving layer

---

### 6.7 Ray Serve / Ray Serve LLM

Ray Serve is useful when you want to build not just a model server, but a larger distributed application around it.

**Best when**

- you need programmable Python orchestration
- you want multi-node / multi-GPU serving
- you want to combine serving with agent pipelines or larger applications

---

## 7) How I would choose among them

### If the goal is an quick systems demo

Stick with:

- vLLM
- or compare vLLM with TGI

These are the cleanest pair conceptually.

---

### If the goal is best performance on NVIDIA GPUs

Use:

- TensorRT-LLM + Triton

---

### If the goal is Kubernetes-native enterprise deployment

Use:

- KServe as the serving platform
- and run vLLM or a Hugging Face runtime under it

---

### If the goal is small local deployment

Use:

- Ollama
- llama.cpp

---

### If the goal is advanced serving research

Use:

- SGLang

---

## 8) Practical recommendation

Because the setup already has Kubeflow + GPU, the best “other options we can build” are:

1. **vLLM on its own** for the core demo
2. **TGI** as the best apples-to-apples comparison server
3. **KServe + vLLM** as the production-grade Kubernetes version of the same idea
4. **TensorRT-LLM + Triton** if you want a second phase focused on NVIDIA optimization

### Suggested expansion path

- **Phase 1:** vLLM demo
- **Phase 2:** vLLM vs TGI comparison
- **Phase 3:** wrap the winning backend inside KServe on Kubeflow
- **Phase 4:** optional NVIDIA-optimized deployment with Triton + TensorRT-LLM
