import math

class LLMTraceGenerator:
    def __init__(self, model_config, ssd_config, output_file):
        self.model_config = model_config
        self.ssd_config = ssd_config
        self.output_file = output_file
        
        self.sector_size = 512
        self.bytes_per_param = 2  # FP16
        
        # MQSim ASCII Format Constants
        self.OP_WRITE = 0
        self.OP_READ = 1
        self.DEVICE_NUM = 0
        self.ROBUST_SENSITIVE = 0
        
    def calculate_layer_params(self):
        hidden = self.model_config['hidden_size']
        interim = self.model_config['intermediate_size']
        attn_params = 4 * (hidden * hidden)
        ffn_params = 3 * (hidden * interim)
        return attn_params + ffn_params

    def generate(self, generation_length=1, prefill_model=True):
        """
        :param generation_length: 토큰 생성 반복 횟수
        :param prefill_model: True일 경우 초기에 모델 Write 트레이스 포함
        """
        params_per_layer = self.calculate_layer_params()
        layer_size_bytes = params_per_layer * self.bytes_per_param
        
        total_sectors_per_layer = math.ceil(layer_size_bytes / self.sector_size)
        max_req_sectors = self.ssd_config['max_request_size_kb'] * 1024 // self.sector_size
        
        # GPU 연산 시간
        compute_time_per_layer_ns = self.model_config.get('layer_compute_time_ns', 10000000)
        
        current_time_ns = 0
        
        with open(self.output_file, 'w') as f:
            
            # ==========================================
            # Phase 1: Model Pre-fill (Write Phase)
            # ==========================================
            if prefill_model:
                print("[Phase 1] Generating Model Write (Pre-fill) trace...")
                current_lba = 0
                
                for layer in range(self.model_config['num_layers']):
                    sectors_remaining = total_sectors_per_layer
                    # 쓰기는 보통 읽기보다 병목이 덜하지만(Buffer), 여기서는 PCIe 전송 속도 반영
                    request_interval_ns = 150 
                    
                    while sectors_remaining > 0:
                        req_size = min(sectors_remaining, max_req_sectors)
                        
                        # Type 0 (Write)
                        trace_line = f"{current_time_ns} {self.DEVICE_NUM} {current_lba} {req_size} {self.OP_WRITE}\n" # {self.ROBUST_SENSITIVE}\n"
                        f.write(trace_line)
                        
                        current_lba += req_size
                        sectors_remaining -= req_size
                        current_time_ns += request_interval_ns
                
                print(f" -> Model Installed. End LBA: {current_lba}")
                
                # 쓰기 완료 후 읽기 시작 전까지 충분한 유휴 시간(Idle)을 둠 (예: 1초)
                # SSD 내부 GC(Garbage Collection)나 Mapping Table 업데이트 등을 고려
                current_time_ns += 1_000_000_000_000

            # ==========================================
            # Phase 2: Inference (Read Phase)
            # ==========================================
            print(f"[Phase 2] Generating Inference Read trace ({generation_length} tokens)...")
            
            for token_idx in range(generation_length):
                # 읽기는 다시 처음(LBA 0)부터 시작
                current_lba = 0 
                
                for layer in range(self.model_config['num_layers']):
                    sectors_remaining = total_sectors_per_layer
                    request_interval_ns = 100
                    
                    while sectors_remaining > 0:
                        req_size = min(sectors_remaining, max_req_sectors)
                        
                        # Type 1 (Read)
                        trace_line = f"{current_time_ns} {self.DEVICE_NUM} {current_lba} {req_size} {self.OP_READ}\n" # {self.ROBUST_SENSITIVE}\n"
                        f.write(trace_line)
                        
                        current_lba += req_size
                        sectors_remaining -= req_size
                        current_time_ns += request_interval_ns
                    
                    # Compute Time Delay
                    current_time_ns += compute_time_per_layer_ns

        print(f"[Done] Trace saved to {self.output_file}. Total duration: {current_time_ns/1e9:.4f} sec")

# --- 설정 및 실행 ---
llama_7b_config = {
    'hidden_size': 4096,
    'intermediate_size': 11008,
    'num_layers': 32,
    'layer_compute_time_ns': 20 * 1000 * 1000 
}

ssd_config = {
    'max_request_size_kb': 256,
}

import sys
gen_len = int(sys.argv[1])

generator = LLMTraceGenerator(
    model_config=llama_7b_config,
    ssd_config=ssd_config,
    output_file=f"llama_7b_gen_{gen_len}_tok.trace"
)

# Pre-fill(Write) 후 3개의 토큰 생성(Read 반복)
generator.generate(generation_length=gen_len, prefill_model=False)