#include "LLM_Workload_Generator.h"
#include <iostream>
#include <string>

using namespace SSD_Components;

void print_usage(const char* prog_name) {
    std::cout << "Usage: " << prog_name << " [options]" << std::endl;
    std::cout << "Options:" << std::endl;
    std::cout << "  -m <model>    Model name: llama7b, llama13b, llama70b, opt6.7b (default: llama7b)" << std::endl;
    std::cout << "  -n <tokens>   Number of tokens to simulate (for stats only, use Relay_Count in XML)" << std::endl;
    std::cout << "  -o <file>     Output trace file (default: llm_trace.txt)" << std::endl;
    std::cout << "  -t <type>     Trace type: compact, decode, full (default: compact)" << std::endl;
    std::cout << "                  compact = single iteration (recommended, use with Relay_Count)" << std::endl;
    std::cout << "                  decode  = full token sequence (large file)" << std::endl;
    std::cout << "                  full    = prefill + decode (very large file)" << std::endl;
    std::cout << "  -c <compute>  Compute time per token in us (default: 1000)" << std::endl;
    std::cout << "  -h            Show this help message" << std::endl;
}

int main(int argc, char* argv[]) {
    // Default parameters
    std::string model_name = "llama7b";
    unsigned int num_tokens = 10000;
    std::string output_file = "llm_trace.txt";
    std::string trace_type = "compact";  // Changed default to compact
    double compute_time_us = 1000.0;

    // Parse command line arguments
    for (int i = 1; i < argc; i++) {
        std::string arg = argv[i];
        if (arg == "-h") {
            print_usage(argv[0]);
            return 0;
        } else if (arg == "-m" && i + 1 < argc) {
            model_name = argv[++i];
        } else if (arg == "-n" && i + 1 < argc) {
            num_tokens = std::stoul(argv[++i]);
        } else if (arg == "-o" && i + 1 < argc) {
            output_file = argv[++i];
        } else if (arg == "-t" && i + 1 < argc) {
            trace_type = argv[++i];
        } else if (arg == "-c" && i + 1 < argc) {
            compute_time_us = std::stod(argv[++i]);
        }
    }

    // Select model
    LLM_Model_Spec model;
    if (model_name == "llama7b") {
        model = LLM_Model_Spec::Llama2_7B();
    } else if (model_name == "llama13b") {
        model = LLM_Model_Spec::Llama2_13B();
    } else if (model_name == "llama70b") {
        model = LLM_Model_Spec::Llama2_70B();
    } else if (model_name == "opt6.7b") {
        model = LLM_Model_Spec::OPT_6_7B();
    } else {
        std::cerr << "Unknown model: " << model_name << std::endl;
        return 1;
    }

    // Configure inference
    LLM_Inference_Config config;
    config.num_tokens_to_generate = num_tokens;
    config.compute_time_per_token_us = compute_time_us;

    // SSD configuration (matches typical Cambricon-LLM setup)
    unsigned long long ssd_capacity = 256ULL * 1024 * 1024 * 1024; // 256GB
    unsigned int page_size = 16 * 1024; // 16KB
    unsigned int pages_per_block = 256;

    std::cout << "\n=== LLM Trace Generator ===" << std::endl;
    std::cout << "Model: " << model.name << std::endl;
    std::cout << "Tokens to generate: " << num_tokens << std::endl;
    std::cout << "Output file: " << output_file << std::endl;
    std::cout << "Trace type: " << trace_type << std::endl;
    std::cout << "==========================\n" << std::endl;

    // Create generator
    LLM_Workload_Generator generator(model, config, ssd_capacity, page_size, pages_per_block);

    // Print statistics
    generator.print_workload_stats();

    // Generate trace
    try {
        if (trace_type == "compact") {
            generator.generate_single_iteration_trace(output_file);
        } else if (trace_type == "decode") {
            std::cout << "WARNING: Generating full decode trace (large file)!" << std::endl;
            generator.generate_decode_trace(output_file);
        } else if (trace_type == "full") {
            std::cout << "WARNING: Generating full prefill+decode trace (very large file)!" << std::endl;
            generator.generate_full_inference_trace(output_file);
        } else {
            std::cerr << "Unknown trace type: " << trace_type << std::endl;
            return 1;
        }
    } catch (const std::exception& e) {
        std::cerr << "Error: " << e.what() << std::endl;
        return 1;
    }

    std::cout << "\nTrace generation successful!" << std::endl;
    return 0;
}
