#ifndef LLM_WORKLOAD_GENERATOR_H
#define LLM_WORKLOAD_GENERATOR_H

#include <string>
#include <vector>
#include <fstream>
#include <cmath>
#include <iostream>
#include <algorithm>
#include <stdexcept>

namespace SSD_Components
{
    // LLM model specifications
    struct LLM_Model_Spec {
        std::string name;
        unsigned long long size_bytes;      // Total model size in bytes
        unsigned int num_layers;            // Number of transformer layers
        unsigned int hidden_dim;            // Hidden dimension size
        unsigned long long weights_per_layer; // Bytes per layer

        // Popular models (INT8 quantization)
        static LLM_Model_Spec Llama2_7B() {
            return {"Llama2-7B", 7ULL * 1024 * 1024 * 1024, 32, 4096,
                    (7ULL * 1024 * 1024 * 1024) / 32};
        }

        static LLM_Model_Spec Llama2_13B() {
            return {"Llama2-13B", 13ULL * 1024 * 1024 * 1024, 40, 5120,
                    (13ULL * 1024 * 1024 * 1024) / 40};
        }

        static LLM_Model_Spec Llama2_70B() {
            return {"Llama2-70B", 70ULL * 1024 * 1024 * 1024, 80, 8192,
                    (70ULL * 1024 * 1024 * 1024) / 80};
        }

        static LLM_Model_Spec OPT_6_7B() {
            return {"OPT-6.7B", 7ULL * 1024 * 1024 * 1024, 32, 4096,
                    (7ULL * 1024 * 1024 * 1024) / 32};
        }
    };

    // Inference configuration
    struct LLM_Inference_Config {
        unsigned int num_tokens_to_generate;  // e.g., 10000, 50000, 100000
        unsigned int prefill_length;          // Initial prompt length (default: 512)
        unsigned int batch_size;              // Always 1 for edge inference
        double compute_time_per_token_us;     // Compute delay between reads (microseconds)

        LLM_Inference_Config() :
            num_tokens_to_generate(10000),
            prefill_length(512),
            batch_size(1),
            compute_time_per_token_us(1000.0) // 1ms default
        {}
    };

    class LLM_Workload_Generator
    {
    private:
        LLM_Model_Spec model;
        LLM_Inference_Config config;
        unsigned long long ssd_capacity_bytes;
        unsigned int page_size_bytes;
        unsigned int pages_per_block;

        // Weight placement tracking
        struct WeightBlock {
            unsigned long long lba_start;
            unsigned long long lba_end;
            unsigned int layer_id;
            std::string matrix_name; // "Q_proj", "K_proj", "V_proj", "O_proj", "FFN1", "FFN2"
        };

        std::vector<WeightBlock> weight_blocks;

    public:
        LLM_Workload_Generator(
            const LLM_Model_Spec& model_spec,
            const LLM_Inference_Config& inference_config,
            unsigned long long ssd_capacity,
            unsigned int page_size,
            unsigned int pages_per_blk
        ) : model(model_spec),
            config(inference_config),
            ssd_capacity_bytes(ssd_capacity),
            page_size_bytes(page_size),
            pages_per_block(pages_per_blk)
        {
            generate_weight_layout();
        }

        // Generate weight placement layout
        void generate_weight_layout() {
            weight_blocks.clear();

            unsigned long long current_lba = 0;
            unsigned long long sectors_per_page = page_size_bytes / 512;

            // Each transformer layer has 6 main weight matrices:
            // Q_proj, K_proj, V_proj, O_proj (attention), FFN1, FFN2 (feed-forward)
            std::vector<std::string> matrix_names = {
                "Q_proj", "K_proj", "V_proj", "O_proj", "FFN1", "FFN2"
            };

            for (unsigned int layer = 0; layer < model.num_layers; layer++) {
                unsigned long long layer_weight_bytes = model.weights_per_layer;
                unsigned long long matrix_weight_bytes = layer_weight_bytes / matrix_names.size();

                for (const auto& matrix_name : matrix_names) {
                    WeightBlock wb;
                    wb.lba_start = current_lba;
                    wb.lba_end = current_lba + (matrix_weight_bytes / 512) - 1;
                    wb.layer_id = layer;
                    wb.matrix_name = matrix_name;

                    weight_blocks.push_back(wb);
                    current_lba = wb.lba_end + 1;
                }
            }

            std::cout << "Generated weight layout for " << model.name << std::endl;
            std::cout << "Total weight blocks: " << weight_blocks.size() << std::endl;
            std::cout << "Total LBA range: 0 to " << current_lba << std::endl;
        }

        // Generate trace file for decode phase (token-by-token generation)
        void generate_decode_trace(const std::string& output_file) {
            std::ofstream trace(output_file);
            if (!trace.is_open()) {
                throw std::runtime_error("Cannot open trace file: " + output_file);
            }

            trace << "# LLM Decode Phase Trace" << std::endl;
            trace << "# Model: " << model.name << std::endl;
            trace << "# Tokens to generate: " << config.num_tokens_to_generate << std::endl;
            trace << "# Format: arrival_time(us) device_id lba size_sectors read/write(1/0)" << std::endl;

            unsigned long long timestamp_us = 0;
            unsigned int device_id = 0;

            // Decode phase: Generate tokens one by one
            for (unsigned int token = 0; token < config.num_tokens_to_generate; token++) {
                // Each token generation reads ALL weight matrices sequentially
                for (const auto& wb : weight_blocks) {
                    unsigned long long lba = wb.lba_start;
                    unsigned long long remaining_sectors = wb.lba_end - wb.lba_start + 1;

                    // Read the entire weight matrix in page-sized chunks
                    while (remaining_sectors > 0) {
                        unsigned long long sectors_to_read = std::min(
                            remaining_sectors,
                            (unsigned long long)(page_size_bytes / 512)
                        );

                        // Format: timestamp device_id lba size read(1)
                        trace << timestamp_us << " "
                              << device_id << " "
                              << lba << " "
                              << sectors_to_read << " "
                              << "1" << std::endl;  // 1 = read

                        lba += sectors_to_read;
                        remaining_sectors -= sectors_to_read;

                        // Small delay between page reads (flash read latency ~30us)
                        timestamp_us += 30;
                    }
                }

                // Add compute time for GEMV operations and special functions
                timestamp_us += (unsigned long long)config.compute_time_per_token_us;

                // Progress indicator
                if ((token + 1) % 1000 == 0) {
                    std::cout << "Generated trace for " << (token + 1)
                              << " tokens (time: " << (timestamp_us / 1000000.0)
                              << " seconds)" << std::endl;
                }
            }

            trace.close();
            std::cout << "Trace generation complete: " << output_file << std::endl;
            std::cout << "Total simulation time: " << (timestamp_us / 1000000.0)
                      << " seconds" << std::endl;
        }

        // Generate mixed prefill + decode trace (more realistic)
        void generate_full_inference_trace(const std::string& output_file) {
            std::ofstream trace(output_file);
            if (!trace.is_open()) {
                throw std::runtime_error("Cannot open trace file: " + output_file);
            }

            trace << "# LLM Full Inference Trace (Prefill + Decode)" << std::endl;
            trace << "# Model: " << model.name << std::endl;
            trace << "# Prefill length: " << config.prefill_length << std::endl;
            trace << "# Tokens to generate: " << config.num_tokens_to_generate << std::endl;

            unsigned long long timestamp_us = 0;
            unsigned int device_id = 0;

            // Phase 1: Prefill (process initial prompt)
            // In prefill, KV cache is being built, so we have matrix-matrix ops
            // Still need to read all weights, but compute time is longer
            trace << "# PREFILL PHASE START" << std::endl;

            for (const auto& wb : weight_blocks) {
                unsigned long long lba = wb.lba_start;
                unsigned long long remaining_sectors = wb.lba_end - wb.lba_start + 1;

                while (remaining_sectors > 0) {
                    unsigned long long sectors_to_read = std::min(
                        remaining_sectors,
                        (unsigned long long)(page_size_bytes / 512)
                    );

                    trace << timestamp_us << " " << device_id << " "
                          << lba << " " << sectors_to_read << " 1" << std::endl;

                    lba += sectors_to_read;
                    remaining_sectors -= sectors_to_read;
                    timestamp_us += 30;
                }
            }

            // Prefill compute time (longer than decode)
            timestamp_us += (unsigned long long)(config.compute_time_per_token_us * config.prefill_length * 0.5);

            trace << "# DECODE PHASE START" << std::endl;

            // Phase 2: Decode (same as generate_decode_trace)
            for (unsigned int token = 0; token < config.num_tokens_to_generate; token++) {
                for (const auto& wb : weight_blocks) {
                    unsigned long long lba = wb.lba_start;
                    unsigned long long remaining_sectors = wb.lba_end - wb.lba_start + 1;

                    while (remaining_sectors > 0) {
                        unsigned long long sectors_to_read = std::min(
                            remaining_sectors,
                            (unsigned long long)(page_size_bytes / 512)
                        );

                        trace << timestamp_us << " " << device_id << " "
                              << lba << " " << sectors_to_read << " 1" << std::endl;

                        lba += sectors_to_read;
                        remaining_sectors -= sectors_to_read;
                        timestamp_us += 30;
                    }
                }

                timestamp_us += (unsigned long long)config.compute_time_per_token_us;

                if ((token + 1) % 1000 == 0) {
                    std::cout << "Generated trace for " << (token + 1) << " tokens" << std::endl;
                }
            }

            trace.close();
            std::cout << "Full inference trace complete: " << output_file << std::endl;
        }

        // Generate single-iteration trace (EFFICIENT - for use with Relay_Count)
        void generate_single_iteration_trace(const std::string& output_file) {
            std::ofstream trace(output_file);
            if (!trace.is_open()) {
                throw std::runtime_error("Cannot open trace file: " + output_file);
            }

            trace << "# LLM Single-Iteration Trace (Compact)" << std::endl;
            trace << "# Model: " << model.name << std::endl;
            trace << "# This trace represents ONE token generation (one pass through all weights)" << std::endl;
            trace << "# To simulate N tokens, use <Relay_Count>N</Relay_Count> in workload config" << std::endl;
            trace << "# Compute time per iteration: " << config.compute_time_per_token_us << " us" << std::endl;
            trace << "# Format: arrival_time(us) device_id lba size_sectors read/write(1/0)" << std::endl;

            unsigned long long timestamp_us = 0;
            unsigned int device_id = 0;

            // Single iteration: Read ALL weight matrices once
            for (const auto& wb : weight_blocks) {
                unsigned long long lba = wb.lba_start;
                unsigned long long remaining_sectors = wb.lba_end - wb.lba_start + 1;

                // Read the entire weight matrix in page-sized chunks
                while (remaining_sectors > 0) {
                    unsigned long long sectors_to_read = std::min(
                        remaining_sectors,
                        (unsigned long long)(page_size_bytes / 512)
                    );

                    // Format: timestamp device_id lba size read(1)
                    trace << timestamp_us << " "
                          << device_id << " "
                          << lba << " "
                          << sectors_to_read << " "
                          << "1" << std::endl;  // 1 = read

                    lba += sectors_to_read;
                    remaining_sectors -= sectors_to_read;

                    // Small delay between page reads (flash read latency ~30us)
                    timestamp_us += 30;
                }
            }

            // Add compute time for GEMV operations and special functions at the end
            timestamp_us += (unsigned long long)config.compute_time_per_token_us;

            trace.close();

            std::cout << "Single-iteration trace complete: " << output_file << std::endl;
            std::cout << "Iteration duration: " << (timestamp_us / 1000.0) << " ms" << std::endl;
            std::cout << "\nTo simulate " << config.num_tokens_to_generate << " tokens:" << std::endl;
            std::cout << "  Set <Relay_Count>" << config.num_tokens_to_generate
                      << "</Relay_Count> in workload XML" << std::endl;
            std::cout << "  Total simulation time: "
                      << (timestamp_us * config.num_tokens_to_generate / 1000000.0)
                      << " seconds" << std::endl;

            // Calculate file size savings
            unsigned long long full_trace_lines = weight_blocks.size() * 100 * config.num_tokens_to_generate; // approximate
            unsigned long long compact_trace_lines = weight_blocks.size() * 100; // approximate
            std::cout << "  File size: ~" << (compact_trace_lines * 30 / (1024.0 * 1024.0))
                      << " MB (vs ~" << (full_trace_lines * 30 / (1024.0 * 1024.0 * 1024.0))
                      << " GB for full trace)" << std::endl;
        }

        // Get statistics about the workload
        void print_workload_stats() {
            std::cout << "\n=== LLM Workload Statistics ===" << std::endl;
            std::cout << "Model: " << model.name << std::endl;
            std::cout << "Total size: " << (model.size_bytes / (1024.0 * 1024 * 1024)) << " GB" << std::endl;
            std::cout << "Layers: " << model.num_layers << std::endl;
            std::cout << "Weight blocks: " << weight_blocks.size() << std::endl;

            unsigned long long total_reads_per_token = 0;
            for (const auto& wb : weight_blocks) {
                total_reads_per_token += (wb.lba_end - wb.lba_start + 1);
            }

            std::cout << "Reads per token: " << total_reads_per_token << " sectors ("
                      << (total_reads_per_token * 512.0 / (1024 * 1024 * 1024)) << " GB)" << std::endl;
            std::cout << "Total reads for " << config.num_tokens_to_generate << " tokens: "
                      << (total_reads_per_token * config.num_tokens_to_generate * 512.0 / (1024.0 * 1024 * 1024 * 1024))
                      << " TB" << std::endl;

            // Calculate average reads per block over the campaign
            unsigned long long total_lba_space = weight_blocks.back().lba_end + 1;
            unsigned long long sectors_per_block = (pages_per_block * page_size_bytes) / 512;
            unsigned long long num_blocks = (total_lba_space + sectors_per_block - 1) / sectors_per_block;

            double avg_reads_per_block = (double)(total_reads_per_token * config.num_tokens_to_generate) / num_blocks;

            std::cout << "Estimated blocks used: " << num_blocks << std::endl;
            std::cout << "Average reads per block: " << avg_reads_per_block << std::endl;
            std::cout << "================================\n" << std::endl;
        }
    };
}

#endif // LLM_WORKLOAD_GENERATOR_H
